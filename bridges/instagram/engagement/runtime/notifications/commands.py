"""CLI command handling for the Instagram notifications engagement bridge."""

from __future__ import annotations

import json
import sys

from bridges.instagram.engagement.runtime.notifications.ai import install_notifications_ai_hooks
from bridges.instagram.engagement.runtime.notifications.bridge import NotificationsBridge
from bridges.instagram.engagement.runtime.notifications.events import emit_notif_error, emit_notif_json, emit_notif_step
from bridges.instagram.engagement.runtime.notifications.persistence import (
    batch_identity_hash,
    build_known_checker,
    load_actioned_hashes,
    record_notification_action,
    record_scan_notifications,
    resolve_account_id,
)
from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.actions.business.workflows.common.suggestion_session import suggestion_session


def _connect(device_id: str, package_name: str = None, *, restart: bool = True) -> NotificationsBridge:
    bridge = NotificationsBridge(device_id, package_name=package_name)
    if not bridge.connect():
        emit_notif_error("Failed to connect to device")
        sys.exit(1)
    # Only the scan entry point restarts Instagram (fresh state). Per-row actions
    # (accept/ignore/reply) operate on the screen the user just scanned, so they
    # skip the costly force-stop + relaunch and just navigate from the current state.
    if restart:
        bridge.restart_instagram()
    return bridge


def _refresh_own_account(bridge: NotificationsBridge, account_username: str | None) -> str | None:
    """Visit our OWN profile before reading the activity feed, then come back to the feed.

    Two things fall out of a step the scan never took. First, the account's followers /
    following / posts counts are re-read and written to the DB — the activity screen shows
    none of them, so they aged for as long as no other workflow ran. Second, the owning
    account is READ instead of assumed: the activity screen carries no account header, so
    `account_username` is passed in by the front, and when it is missing the whole
    persistence + dedup half is skipped in silence.

    Returns the username to file this scan under (the caller's value wins when it has one,
    so a front that already knows the account keeps deciding).

    Coming back to the feed is not optional: the activity entry lives on the HOME screen.
    Leaving Instagram on the profile page would make `ensure_notifications_screen` fail its
    first attempt and recover by RESTARTING the app — the scan would still work, and would
    quietly cost a relaunch every time. Best-effort throughout: refreshing a counter must
    never cost the scan it rides in on.
    """
    from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
    from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness

    resolved = account_username
    try:
        emit_notif_step(step="own_profile", status="running", message="Refreshing your account")
        profile = ProfileBusiness(bridge.device).get_complete_profile_info(
            username=None, navigate_if_needed=True,
        )
        if profile and profile.get("username"):
            resolved = account_username or profile["username"]
            emit_notif_step(
                step="own_profile", status="done",
                message=f"@{profile['username']} — {profile.get('followers_count', 0)} followers",
            )
        else:
            emit_notif_step(step="own_profile", status="failed", message="Could not read your profile")
    except Exception as exc:
        logger.warning(f"[NOTIF] Own-profile refresh skipped: {exc}")
        emit_notif_step(step="own_profile", status="failed", message="Profile refresh skipped")
    finally:
        try:
            NavigationActions(bridge.device).navigate_to_home()
        except Exception as exc:
            logger.warning(f"[NOTIF] Could not return to the feed after the profile visit: {exc}")
    return resolved


def _run_suggestions_visit(bridge: NotificationsBridge, workflow, *, max_profiles: int,
                           account_username: str | None, ai_config: dict | None,
                           language: str) -> dict:
    """Visit and qualify ``max_profiles`` suggested accounts.

    Every suggestion is an UNKNOWN profile: the surface shows a display label, never
    the @handle. The profile is therefore opened and run through the per-profile
    pipeline, exactly like a target run. That pipeline writes the follows under the
    real handle, so nothing is recorded here.
    """
    result = {"visited": 0, "processed": 0, "follows": 0, "filtered": 0, "errors": 0,
              "profiles": [], "stop_reason": "disabled", "ai_qualification": False}
    account_id = resolve_account_id(account_username or "")
    if account_id is None:
        # Hard refusal: without a resolved account the follows would go under the
        # default id, that is under another account, in the very table the daily caps
        # read.
        result["stop_reason"] = "no_account"
        logger.warning("[NOTIF] No account resolved: suggestions visit skipped")
        emit_notif_step(step="suggestions", status="failed",
                        message="Compte introuvable: visite des suggestions annulee")
        return result

    result["ai_qualification"] = install_notifications_ai_hooks(
        ai_config=ai_config, device=bridge.device, language=language,
    )

    # ONE session for the whole pass, fallback included. Without it the follows are
    # written with no `session_id`: they exist but belong to no session, so they never
    # surface in the history nor in the `stats_*` snapshot.
    with suggestion_session(account_id, source="notifications") as session_id:
        result["session_id"] = session_id
        _run_visit_with_session(bridge, workflow, result, account_id=account_id,
                                session_id=session_id, max_profiles=max_profiles)
    return result


def _run_visit_with_session(bridge: NotificationsBridge, workflow, result: dict, *,
                            account_id: int, session_id, max_profiles: int) -> None:
    """The pass itself, once the session is open."""
    workflow.profile_pipeline = bridge.build_profile_pipeline(
        account_id=account_id, session_id=session_id,
    )

    emit_notif_step(step="suggestions", status="running",
                    message="Visite des comptes suggeres")
    visit = workflow.visit_suggestions(max_profiles=max_profiles)
    result.update({k: visit[k] for k in
                   ("visited", "processed", "follows", "filtered", "errors",
                    "profiles", "stop_reason")})

    # FALLBACK. The section at the bottom of the activity screen is served by the
    # algorithm and changes identity from one pass to the next. When it is not there,
    # the volume is fetched from the dedicated people screen, with the same qualified
    # visit.
    remaining = max_profiles - result["visited"]
    if result["stop_reason"] == "no_suggestions_offered" and remaining > 0:
        emit_notif_step(step="suggestions", status="running",
                        message="Aucune suggestion ici — repli sur Decouvrir des personnes")
        fallback = _run_discover_fallback(bridge, account_id=account_id,
                                          session_id=session_id,
                                          max_profiles=remaining)
        result["fallback"] = fallback
        for key in ("visited", "processed", "follows", "filtered", "errors"):
            result[key] += fallback.get(key, 0)
        result["profiles"].extend(fallback.get("profiles", []))
        result["stop_reason"] = fallback.get("stop_reason", result["stop_reason"])

    emit_notif_step(step="suggestions", status="done",
                    message=f"{result['visited']} profil(s) suggere(s) visite(s), "
                            f"{result['follows']} follow(s)")


def _run_discover_fallback(bridge: NotificationsBridge, *, account_id: int,
                           session_id, max_profiles: int) -> dict:
    """Fetch the suggestions from the dedicated people screen.

    The feed workflow owns that surface and, being a ``BaseBusinessAction``, already
    carries the per-profile pipeline: nothing to inject here.
    """
    from taktik.core.social_media.instagram.actions.business.workflows.feed import FeedBusiness
    from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
    from taktik.core.social_media.instagram.workflows.management.notifications import (
        DEFAULT_SUGGESTION_INTERACTION_CONFIG,
    )

    from taktik.core.social_media.instagram.workflows.management.session import SessionManager

    try:
        # Same session as the notifications zone: this is the SAME acquisition pass,
        # it only changed surface. The SessionManager is what `_get_session_id()` reads
        # to attach each follow; without it the fallback would write orphan
        # interactions again.
        session_manager = SessionManager({"session_settings": {}})
        session_manager.session_id = session_id
        feed = FeedBusiness(DeviceFacade(bridge.device), session_manager=session_manager)
        feed.active_account_id = account_id
        return feed.run_discover_visit_pass(
            dict(DEFAULT_SUGGESTION_INTERACTION_CONFIG), max_profiles=max_profiles,
        )
    except Exception as exc:  # noqa: BLE001 — the fallback must never break the scan
        logger.warning(f"[NOTIF] Discover people fallback failed: {exc}")
        return {"visited": 0, "processed": 0, "follows": 0, "filtered": 0,
                "errors": 0, "profiles": [], "stop_reason": "fallback_error"}


def cmd_scan(device_id: str, limit: int, account_username: str = None,
             package_name: str = None, follow_suggestions: int = 0,
             ai_config: dict = None, language: str = "en") -> None:
    """Read + classify the activity feed (all notification families).

    The scan is a complete run: it force-restarts Instagram to a known state at the
    start, so it also CLOSES it at the end rather than leaving the app open on the
    activity screen. Per-row actions triggered afterwards (accept / ignore / reply /
    like) self-heal through the workflow's relauncher, which is explicitly designed
    for "Instagram drifted elsewhere or was closed since the scan".
    """
    bridge = _connect(device_id, package_name, restart=True)
    # Our own profile FIRST: refreshes the account's counters (the activity screen shows
    # none of them) and reads the owning account instead of trusting the caller for it.
    # Leaves Instagram back on the feed, where the activity entry lives.
    account_username = _refresh_own_account(bridge, account_username)
    # `limit` is interpreted as how many extra screens to scroll (0 = visible only).
    workflow = bridge.build_workflow()
    # Early-stop: recognise notifications already recorded for this account (loaded once) so the
    # scan stops scrolling once it reaches already-seen territory instead of re-scraping history.
    known_checker = build_known_checker(account_username)
    result = workflow.scan(max_scrolls=max(0, limit), known_checker=known_checker)
    items = result.get("items", [])

    # Persist + dedup (best-effort): annotate each item with `is_new` so the front can
    # skip already-processed notifications. The activity screen has no account header, so
    # the owning account is passed in by the front (resolved via getLatestDeviceAccounts).
    try:
        flags = record_scan_notifications(account_username, items)
        for item, is_new in zip(items, flags):
            item["is_new"] = is_new
        # Narrate the dedup outcome in the Taktik Agent panel (only when persistence
        # actually ran, i.e. the owning account was known).
        if account_username:
            new_count = sum(1 for flag in flags if flag)
            if items and new_count == 0:
                emit_notif_step(step="result", status="running",
                                message="No new notifications — all already seen", new_count=0)
            elif new_count:
                emit_notif_step(step="result", status="running",
                                message=f"{new_count} new notification(s)", new_count=new_count)
    except Exception as exc:  # never break the scan on persistence
        logger.warning(f"notifications persistence skipped: {exc}")

    # Suggestions: the block at the very BOTTOM of this screen, which the scan has just
    # scrolled to. Opt-in, and only after the notifications themselves are persisted — a
    # profile visit must never cost us the scan it rode in on.
    suggestions = {"visited": 0, "processed": 0, "follows": 0, "filtered": 0,
                   "errors": 0, "profiles": [], "stop_reason": "disabled",
                   "ai_qualification": False}
    if follow_suggestions > 0:
        try:
            suggestions = _run_suggestions_visit(
                bridge, workflow, max_profiles=follow_suggestions,
                account_username=account_username, ai_config=ai_config, language=language,
            )
        except Exception as exc:
            logger.warning(f"[NOTIF] Suggestions visit failed: {exc}")
            suggestions["stop_reason"] = "error"

    # Leave the phone clean: the scan opened Instagram, the scan closes it.
    bridge.stop()

    # Terminal narration: closes the live notifications card in the Agent panel.
    emit_notif_step(step="session_end", status="done", message="Notifications session complete")

    emit_notif_json({
        "type": "result",
        "command": "scan",
        "success": result.get("success", False),
        "count": result.get("count", 0),
        "by_type": result.get("by_type", {}),
        "items": items,
        "requests": result.get("requests", []),
        "has_grouped_requests": result.get("has_grouped_requests", False),
        "message": result.get("message", ""),
        "suggestions": suggestions,
    }, flush=True)


def cmd_list_requests(device_id: str, limit: int, package_name: str = None) -> None:
    """Enumerate pending follow requests (usernames) on the sub-screen."""
    bridge = _connect(device_id, package_name, restart=False)
    workflow = bridge.build_workflow()
    result = workflow.list_requests(max_requests=limit if limit > 0 else 50)
    emit_notif_json({
        "type": "result",
        "command": "list_requests",
        "success": result.get("success", False),
        "count": result.get("count", 0),
        "requests": result.get("requests", []),
        "message": result.get("message", ""),
    }, flush=True)


def cmd_accept(device_id: str, username: str, package_name: str = None,
               account_username: str = None) -> None:
    bridge = _connect(device_id, package_name, restart=False)
    result = bridge.build_workflow().accept_request(username)
    record_notification_action(account_username, action="accept", actor_username=username,
                               success=bool(result.get("success")))
    emit_notif_json({"type": "result", "command": "accept", **result}, flush=True)


def cmd_ignore(device_id: str, username: str, package_name: str = None,
               account_username: str = None) -> None:
    bridge = _connect(device_id, package_name, restart=False)
    result = bridge.build_workflow().ignore_request(username)
    record_notification_action(account_username, action="ignore", actor_username=username,
                               success=bool(result.get("success")))
    emit_notif_json({"type": "result", "command": "ignore", **result}, flush=True)


def cmd_accept_all(device_id: str, limit: int, package_name: str = None,
                   account_username: str = None) -> None:
    bridge = _connect(device_id, package_name, restart=False)
    result = bridge.build_workflow().accept_all_requests(max_requests=limit if limit > 0 else 50)
    for accepted in result.get("accepted", []):
        record_notification_action(account_username, action="accept", actor_username=accepted,
                                   success=True, source="batch")
    emit_notif_json({
        "type": "result",
        "command": "accept_all",
        "success": result.get("success", False),
        "count": result.get("count", 0),
        "accepted": result.get("accepted", []),
        "message": result.get("message", ""),
    }, flush=True)


def cmd_reply(device_id: str, username: str, text: str = "", package_name: str = None,
              account_username: str = None) -> None:
    """Reply to ``username``'s comment/mention with ``text`` (click-in + type + send).

    Empty ``text`` opens the reply UI only (operator types by hand on the device) —
    nothing is sent by our hand, so nothing is recorded.
    """
    bridge = _connect(device_id, package_name, restart=False)
    result = bridge.build_workflow().reply_to_comment(username, text)
    if text.strip():
        record_notification_action(account_username, action="reply", actor_username=username,
                                   success=bool(result.get("success")), content=text)
    emit_notif_json({"type": "result", "command": "reply", **result}, flush=True)


def cmd_like(device_id: str, username: str, package_name: str = None,
             account_username: str = None) -> None:
    """Like the comment / mention of ``username`` inline from the feed."""
    bridge = _connect(device_id, package_name, restart=False)
    result = bridge.build_workflow().like_comment(username)
    record_notification_action(account_username, action="like", actor_username=username,
                               success=bool(result.get("success")))
    emit_notif_json({"type": "result", "command": "like", **result}, flush=True)


def cmd_follow_back(device_id: str, username: str, package_name: str = None,
                    account_username: str = None) -> None:
    """Follow ``username`` back inline from their "started following you" row."""
    bridge = _connect(device_id, package_name, restart=False)
    result = bridge.build_workflow().follow_back(username)
    record_notification_action(account_username, action="follow_back", actor_username=username,
                               success=bool(result.get("success")))
    emit_notif_json({"type": "result", "command": "follow_back", **result}, flush=True)


def cmd_batch(device_id: str, actions: list[dict], package_name: str = None,
              account_username: str = None, source: str = "batch") -> None:
    """Run a LIST of notification actions inside ONE session.

    Every action used to be its own bridge invocation: a Python process, a fresh uiautomator2
    connection, a walk back to the activity feed — and, front-side, a network-pool lease taken and
    released. Liking four comments paid that four times, and answering ten reviewed AI drafts paid
    it ten times. Here the connection is made once and the workflow is reused, which is what
    ``accept_all`` has always done for follow requests; this generalises it to the other actions.

    A ``notification_step`` is emitted BEFORE each action and after each result, so the front can
    show real progress — and so that a batch killed mid-way has already reported everything that
    did happen. Stop is a process kill by design (the operator asked to stop, not to finish the
    current one), so nothing here polls a flag: the last emitted step IS the record.

    Each action is ``{"action": "like"|"reply"|"accept"|"ignore"|"follow_back",
    "username": str, "text": str?}`` plus an OPTIONAL notification identity
    ``notif_type`` / ``notif_text`` / ``notif_time`` (``text`` is already taken by the
    reply body, hence the prefix). When the identity is there, the entry's stable
    content_hash is computed and the action becomes IDEMPOTENT across scans: an action
    already recorded as succeeded for this account is skipped (``skipped: true`` in its
    result) instead of re-tapped — the autopilot's belt-and-braces above the scan's
    ``is_new``. Executed actions are recorded (audit + budget interactions), see
    ``record_notification_action``.

    One failing action does not abort the rest — a comment whose row scrolled out of reach must not
    cancel the nine others.
    """
    bridge = _connect(device_id, package_name, restart=False)
    workflow = bridge.build_workflow()

    total = len(actions)
    results: list[dict] = []
    done = 0
    failed = 0
    skipped = 0
    # Preloaded once per verb present in the batch (no per-action DB hit).
    actioned_by_verb: dict[str, set] = {}

    for index, entry in enumerate(actions):
        action = (entry.get("action") or "").strip()
        username = (entry.get("username") or "").strip()
        text = entry.get("text") or ""
        identity = None
        if entry.get("notif_type") or entry.get("notif_text"):
            identity = {"ntype": entry.get("notif_type"), "actor": username,
                        "text": entry.get("notif_text"), "time": entry.get("notif_time")}
        entry_hash = batch_identity_hash(account_username, identity)

        if entry_hash:
            if action not in actioned_by_verb:
                actioned_by_verb[action] = load_actioned_hashes(account_username, action)
            if entry_hash in actioned_by_verb[action]:
                skipped += 1
                results.append({"action": action, "username": username,
                                "success": True, "skipped": True,
                                "message": f"Already {action}ed — skipped"})
                emit_notif_json({
                    "type": "notification_step", "step": "batch_result",
                    "index": index, "total": total, "action": action,
                    "username": username, "success": True,
                    "message": f"[{index + 1}/{total}] {action} @{username} already done — skipped",
                }, flush=True)
                continue

        emit_notif_json({
            "type": "notification_step",
            "step": "batch_action",
            "index": index,
            "total": total,
            "action": action,
            "username": username,
            "message": f"[{index + 1}/{total}] {action} @{username}",
        }, flush=True)

        try:
            if action == "like":
                result = workflow.like_comment(username)
            elif action == "reply":
                result = workflow.reply_to_comment(username, text)
            elif action == "accept":
                result = workflow.accept_request(username)
            elif action == "ignore":
                result = workflow.ignore_request(username)
            elif action == "follow_back":
                result = workflow.follow_back(username)
            else:
                result = {"success": False, "error": f"Unknown action: {action}"}
        except Exception as exc:  # noqa: BLE001
            # Isolated per action, on purpose: see the docstring.
            logger.error(f"[NOTIF] batch {action} @{username} failed: {exc}")
            result = {"success": False, "error": str(exc)}

        ok = bool(result.get("success"))
        done += 1 if ok else 0
        failed += 0 if ok else 1
        results.append({"action": action, "username": username, **result})

        # Bookkeeping: audit row (+ budget interaction on success) for every EXECUTED
        # action; a nothing-sent reply (empty text opens the UI only) records nothing.
        if action != "reply" or text.strip():
            record_notification_action(
                account_username, action=action, actor_username=username,
                identity=identity, success=ok, source=source,
                content=text if action == "reply" else None,
            )
            if ok and entry_hash:
                actioned_by_verb.setdefault(action, set()).add(entry_hash)

        emit_notif_json({
            "type": "notification_step",
            "step": "batch_result",
            "index": index,
            "total": total,
            "action": action,
            "username": username,
            "success": ok,
            "message": f"[{index + 1}/{total}] {action} @{username} {'ok' if ok else 'failed'}",
        }, flush=True)

    emit_notif_json({
        "type": "result",
        "command": "batch",
        "success": failed == 0,
        "total": total,
        "done": done,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }, flush=True)


def run_notifications_cli(args: list[str]) -> None:
    """Parse notifications bridge CLI args and dispatch the selected command."""
    package_name = None
    if "--package" in args:
        idx = args.index("--package")
        if idx + 1 < len(args):
            package_name = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    # The owning account (the front resolves it via getLatestDeviceAccounts) — used by
    # `scan` to persist + dedup notifications (the activity screen has no header), and by
    # every ACTION command to record what was done (audit + budget interactions).
    account_username = None
    if "--account" in args:
        idx = args.index("--account")
        if idx + 1 < len(args):
            account_username = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    # Who triggered a batch: 'batch' (operator selection, default) or 'autopilot'
    # (policy-driven, e.g. auto-like after a scan). Recorded in notification_actions.
    batch_source = "batch"
    if "--source" in args:
        idx = args.index("--source")
        if idx + 1 < len(args):
            batch_source = (args[idx + 1] or "batch").strip() or "batch"
            args = args[:idx] + args[idx + 2:]

    # Opt-in: how many suggested accounts to VISIT at the END of a scan, from the block
    # at the bottom of the activity screen. Absent / 0 = the scan behaves exactly as before.
    follow_suggestions = 0
    if "--follow-suggestions" in args:
        idx = args.index("--follow-suggestions")
        if idx + 1 < len(args):
            try:
                follow_suggestions = max(0, int(args[idx + 1]))
            except ValueError:
                follow_suggestions = 0
            args = args[:idx] + args[idx + 2:]

    # AI qualification for the visited profiles (same shape as the automation bridge's
    # `ai` config block). Absent = the visit still extracts / persists / follows, but the
    # profiles are not qualified — and the run log says so rather than staying silent.
    ai_config = None
    if "--ai-config" in args:
        idx = args.index("--ai-config")
        if idx + 1 < len(args):
            raw = args[idx + 1]
            try:
                ai_config = json.loads(raw)
            except (TypeError, ValueError) as exc:
                logger.warning(f"[NOTIF] Unreadable --ai-config ({exc}): AI qualification off")
                ai_config = None
            args = args[:idx] + args[idx + 2:]

    # App language: only used to pick the language of the AI's own wording.
    language = "en"
    if "--language" in args:
        idx = args.index("--language")
        if idx + 1 < len(args):
            language = args[idx + 1] or "en"
            args = args[:idx] + args[idx + 2:]

    if not args:
        emit_notif_error(
            "Usage: notifications.py <command> [args] [--package <pkg>] [--account <username>]\n"
            "       [--follow-suggestions <n>] [--ai-config <json>] [--language <code>]\n"
            "       [--source <batch|autopilot>]\n"
            "  scan <device_id> [scroll]\n"
            "  list_requests <device_id> [limit]\n"
            "  accept <device_id> <username>\n"
            "  ignore <device_id> <username>\n"
            "  accept_all <device_id> [max]\n"
            "  reply <device_id> <username> [text]\n"
            "  like <device_id> <username>\n"
            "  follow_back <device_id> <username>\n"
            '  batch <device_id> \'[{"action":"like","username":"x"},...]\''
        )
        sys.exit(1)

    command = args[0]

    try:
        if command == "scan":
            if len(args) < 2:
                emit_notif_error("Usage: notifications.py scan <device_id> [scroll] [--account <username>]")
                sys.exit(1)
            cmd_scan(args[1], int(args[2]) if len(args) > 2 else 3,
                     follow_suggestions=follow_suggestions,
                     account_username=account_username, package_name=package_name,
                     ai_config=ai_config, language=language)

        elif command == "list_requests":
            if len(args) < 2:
                emit_notif_error("Usage: notifications.py list_requests <device_id> [limit]")
                sys.exit(1)
            cmd_list_requests(args[1], int(args[2]) if len(args) > 2 else 50, package_name=package_name)

        elif command == "accept":
            if len(args) < 3:
                emit_notif_error("Usage: notifications.py accept <device_id> <username>")
                sys.exit(1)
            cmd_accept(args[1], args[2], package_name=package_name,
                       account_username=account_username)

        elif command == "ignore":
            if len(args) < 3:
                emit_notif_error("Usage: notifications.py ignore <device_id> <username>")
                sys.exit(1)
            cmd_ignore(args[1], args[2], package_name=package_name,
                       account_username=account_username)

        elif command == "accept_all":
            if len(args) < 2:
                emit_notif_error("Usage: notifications.py accept_all <device_id> [max]")
                sys.exit(1)
            cmd_accept_all(args[1], int(args[2]) if len(args) > 2 else 50,
                           package_name=package_name, account_username=account_username)

        elif command == "reply":
            if len(args) < 3:
                emit_notif_error("Usage: notifications.py reply <device_id> <username> [text]")
                sys.exit(1)
            reply_text = " ".join(args[3:]) if len(args) > 3 else ""
            cmd_reply(args[1], args[2], reply_text, package_name=package_name,
                      account_username=account_username)

        elif command == "like":
            if len(args) < 3:
                emit_notif_error("Usage: notifications.py like <device_id> <username>")
                sys.exit(1)
            cmd_like(args[1], args[2], package_name=package_name,
                     account_username=account_username)

        elif command == "follow_back":
            if len(args) < 3:
                emit_notif_error("Usage: notifications.py follow_back <device_id> <username>")
                sys.exit(1)
            cmd_follow_back(args[1], args[2], package_name=package_name,
                            account_username=account_username)

        elif command == "batch":
            # The action list travels as ONE argv element (spawn, no shell), so unicode and spaces
            # in reply texts survive without quoting rules.
            if len(args) < 3:
                emit_notif_error('Usage: notifications.py batch <device_id> <json_actions>')
                sys.exit(1)
            try:
                parsed = json.loads(args[2])
            except (TypeError, ValueError) as exc:
                emit_notif_error(f"Unreadable batch actions: {exc}")
                sys.exit(1)
            if not isinstance(parsed, list) or not parsed:
                emit_notif_error("Batch actions must be a non-empty list")
                sys.exit(1)
            cmd_batch(args[1], parsed, package_name=package_name,
                      account_username=account_username, source=batch_source)

        else:
            emit_notif_error(f"Unknown command: {command}")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        import traceback

        logger.error(f"notifications bridge error: {exc}")
        emit_notif_json({"success": False, "error": str(exc), "traceback": traceback.format_exc()}, flush=True)
        sys.exit(1)


__all__ = ["run_notifications_cli"]
