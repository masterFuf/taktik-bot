"""The commands of an Instagram notifications run: scan, the per-row verbs and the batch.

Called by `run_instagram_notifications` (the launcher of `instagram.engagement.notifications`),
which the desktop bridge and the CLI both call. What differs between the hosts is the
`NotificationsHost`: how the device is connected (and Instagram restarted), where the events go,
and which AI service qualifies the visited profiles. Each command returns the result the desktop
reads; the events on the way go to `host.emit`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.core.database.account_health import witness_for
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.business.workflows.common.suggestion_session import suggestion_session
from taktik.core.social_media.instagram.workflows.management.notifications.ai import install_notifications_ai_hooks
from taktik.core.social_media.instagram.workflows.management.notifications.follow_actor import (
    FOLLOW_ACTOR_ACTION,
    follow_actor,
)
from taktik.core.social_media.instagram.workflows.management.notifications.notifications_workflow import (
    NotificationsEngagementWorkflow,
)
from taktik.core.social_media.instagram.workflows.management.notifications.persistence import (
    batch_identity_hash,
    build_known_checker,
    count_actions_today,
    load_actioned_hashes,
    record_notification_action,
    record_scan_notifications,
    record_welcome_dm,
    resolve_account_id,
)
from taktik.core.social_media.instagram.workflows.management.notifications.profile_pipeline import (
    build_notifications_profile_pipeline,
)
from taktik.core.social_media.instagram.workflows.management.notifications.welcome_dm import (
    OFF_SCREEN_ACTIONS,
    WELCOME_DM_ACTION,
    order_batch_actions,
    send_welcome_dm,
    wait_before_next_off_screen_action,
    welcome_dm_skip_reason,
)

Emit = Callable[[dict], None]
AIServiceFactory = Callable[[Mapping[str, Any]], Any]


@dataclass
class NotificationsHost:
    """What a host lends a notifications run.

    - `connect(restart)`: the connected runtime (`device`, `device_id`, `restart_instagram()`,
      `stop()`), Instagram restarted first when `restart` is true;
    - `emit(payload)`: the run's events (steps, batch progress);
    - `ai_service(ai_config)`: the AI service that qualifies the visited profiles, or None.
    """

    connect: Callable[[bool], Any]
    emit: Emit
    ai_service: Optional[AIServiceFactory] = None

    def step(self, *, step: str, status: str, message: str = "", **extra) -> None:
        """Per-step live narration."""
        self.emit({"type": "notification_step", "step": step, "step_status": status,
                   "message": message, **extra})


def _build_workflow(host: NotificationsHost, runtime) -> NotificationsEngagementWorkflow:
    # relauncher lets a per-row action self-heal (restart IG + re-navigate) when
    # Instagram has drifted away from the notifications screen since the scan.
    return NotificationsEngagementWorkflow(
        runtime.device, runtime.device_id,
        notifier=host.step,
        relauncher=runtime.restart_instagram,
    )


def _watch_account_health(account_username: str | None) -> None:
    """A block seen during this command becomes one entry of the account's health history."""
    run_halt.configurer_temoin(witness_for(
        "instagram", lambda: account_username, source_type=lambda: "NOTIFICATIONS"))


def _refresh_own_account(host: NotificationsHost, runtime, account_username: str | None) -> str | None:
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
        host.step(step="own_profile", status="running", message="Refreshing your account")
        profile = ProfileBusiness(runtime.device).get_complete_profile_info(
            username=None, navigate_if_needed=True,
        )
        if profile and profile.get("username"):
            resolved = account_username or profile["username"]
            host.step(
                step="own_profile", status="done",
                message=f"@{profile['username']} — {profile.get('followers_count', 0)} followers",
            )
        else:
            host.step(step="own_profile", status="failed", message="Could not read your profile")
    except Exception as exc:
        logger.warning(f"[NOTIF] Own-profile refresh skipped: {exc}")
        host.step(step="own_profile", status="failed", message="Profile refresh skipped")
    finally:
        try:
            NavigationActions(runtime.device).navigate_to_home()
        except Exception as exc:
            logger.warning(f"[NOTIF] Could not return to the feed after the profile visit: {exc}")
    return resolved


def _run_suggestions_visit(host: NotificationsHost, runtime, workflow, *, max_profiles: int,
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
        host.step(step="suggestions", status="failed",
                  message="Compte introuvable: visite des suggestions annulee")
        return result

    result["ai_qualification"] = install_notifications_ai_hooks(
        ai_config=ai_config, device=runtime.device, language=language, ai_service=host.ai_service,
    )

    # ONE session for the whole pass, fallback included. Without it the follows are
    # written with no `session_id`: they exist but belong to no session, so they never
    # surface in the history nor in the `stats_*` snapshot.
    with suggestion_session(account_id, source="notifications") as session_id:
        result["session_id"] = session_id
        _run_visit_with_session(host, runtime, workflow, result, account_id=account_id,
                                session_id=session_id, max_profiles=max_profiles)
    return result


def _run_visit_with_session(host: NotificationsHost, runtime, workflow, result: dict, *,
                            account_id: int, session_id, max_profiles: int) -> None:
    """The pass itself, once the session is open."""
    # Per-profile production pipeline bound to THIS phone's account and session: every
    # follow it lands is written under them, never under a defaulted id.
    workflow.profile_pipeline = build_notifications_profile_pipeline(
        runtime.device, account_id=account_id, session_id=session_id,
    )

    host.step(step="suggestions", status="running", message="Visite des comptes suggeres")
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
        host.step(step="suggestions", status="running",
                  message="Aucune suggestion ici — repli sur Decouvrir des personnes")
        fallback = _run_discover_fallback(runtime, account_id=account_id,
                                          session_id=session_id,
                                          max_profiles=remaining)
        result["fallback"] = fallback
        for key in ("visited", "processed", "follows", "filtered", "errors"):
            result[key] += fallback.get(key, 0)
        result["profiles"].extend(fallback.get("profiles", []))
        result["stop_reason"] = fallback.get("stop_reason", result["stop_reason"])

    host.step(step="suggestions", status="done",
              message=f"{result['visited']} profil(s) suggere(s) visite(s), "
                      f"{result['follows']} follow(s)")


def _run_discover_fallback(runtime, *, account_id: int, session_id, max_profiles: int) -> dict:
    """Fetch the suggestions from the dedicated people screen.

    The feed workflow owns that surface and, being a ``BaseBusinessAction``, already
    carries the per-profile pipeline: nothing to inject here.
    """
    from taktik.core.social_media.instagram.actions.business.workflows.feed import FeedBusiness
    from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
    from taktik.core.social_media.instagram.workflows.management.notifications.profile_pipeline import (
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
        feed = FeedBusiness(DeviceFacade(runtime.device), session_manager=session_manager)
        feed.active_account_id = account_id
        return feed.run_discover_visit_pass(
            dict(DEFAULT_SUGGESTION_INTERACTION_CONFIG), max_profiles=max_profiles,
        )
    except Exception as exc:  # noqa: BLE001 — the fallback must never break the scan
        logger.warning(f"[NOTIF] Discover people fallback failed: {exc}")
        return {"visited": 0, "processed": 0, "follows": 0, "filtered": 0,
                "errors": 0, "profiles": [], "stop_reason": "fallback_error"}


def cmd_scan(host: NotificationsHost, limit: int, account_username: str = None,
             follow_suggestions: int = 0, ai_config: dict = None, language: str = "en") -> dict:
    """Read + classify the activity feed (all notification families).

    The scan is a complete run: it force-restarts Instagram to a known state at the
    start, so it also CLOSES it at the end rather than leaving the app open on the
    activity screen. Per-row actions triggered afterwards (accept / ignore / reply /
    like) self-heal through the workflow's relauncher, which is explicitly designed
    for "Instagram drifted elsewhere or was closed since the scan".
    """
    runtime = host.connect(True)
    # Our own profile FIRST: refreshes the account's counters (the activity screen shows
    # none of them) and reads the owning account instead of trusting the caller for it.
    # Leaves Instagram back on the feed, where the activity entry lives.
    account_username = _refresh_own_account(host, runtime, account_username)
    # `limit` is interpreted as how many extra screens to scroll (0 = visible only).
    workflow = _build_workflow(host, runtime)
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
                host.step(step="result", status="running",
                          message="No new notifications — all already seen", new_count=0)
            elif new_count:
                host.step(step="result", status="running",
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
                host, runtime, workflow, max_profiles=follow_suggestions,
                account_username=account_username, ai_config=ai_config, language=language,
            )
        except Exception as exc:
            logger.warning(f"[NOTIF] Suggestions visit failed: {exc}")
            suggestions["stop_reason"] = "error"

    # Leave the phone clean: the scan opened Instagram, the scan closes it.
    runtime.stop()

    # Terminal narration: closes the live notifications card in the Agent panel.
    host.step(step="session_end", status="done", message="Notifications session complete")

    return {
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
    }


def cmd_list_requests(host: NotificationsHost, limit: int) -> dict:
    """Enumerate pending follow requests (usernames) on the sub-screen."""
    runtime = host.connect(False)
    workflow = _build_workflow(host, runtime)
    result = workflow.list_requests(max_requests=limit if limit > 0 else 50)
    return {
        "type": "result",
        "command": "list_requests",
        "success": result.get("success", False),
        "count": result.get("count", 0),
        "requests": result.get("requests", []),
        "message": result.get("message", ""),
    }


def cmd_accept(host: NotificationsHost, username: str, account_username: str = None) -> dict:
    _watch_account_health(account_username)
    runtime = host.connect(False)
    result = _build_workflow(host, runtime).accept_request(username)
    record_notification_action(account_username, action="accept", actor_username=username,
                               success=bool(result.get("success")))
    return {"type": "result", "command": "accept", **result}


def cmd_ignore(host: NotificationsHost, username: str, account_username: str = None) -> dict:
    _watch_account_health(account_username)
    runtime = host.connect(False)
    result = _build_workflow(host, runtime).ignore_request(username)
    record_notification_action(account_username, action="ignore", actor_username=username,
                               success=bool(result.get("success")))
    return {"type": "result", "command": "ignore", **result}


def cmd_accept_all(host: NotificationsHost, limit: int, account_username: str = None) -> dict:
    _watch_account_health(account_username)
    runtime = host.connect(False)
    result = _build_workflow(host, runtime).accept_all_requests(max_requests=limit if limit > 0 else 50)
    for accepted in result.get("accepted", []):
        record_notification_action(account_username, action="accept", actor_username=accepted,
                                   success=True, source="batch")
    return {
        "type": "result",
        "command": "accept_all",
        "success": result.get("success", False),
        "count": result.get("count", 0),
        "accepted": result.get("accepted", []),
        "message": result.get("message", ""),
        **({"stop_reason": result["stop_reason"]} if result.get("stop_reason") else {}),
    }


def cmd_reply(host: NotificationsHost, username: str, text: str = "",
              account_username: str = None) -> dict:
    """Reply to ``username``'s comment/mention with ``text`` (click-in + type + send).

    Empty ``text`` opens the reply UI only (operator types by hand on the device) —
    nothing is sent by our hand, so nothing is recorded.
    """
    _watch_account_health(account_username)
    runtime = host.connect(False)
    result = _build_workflow(host, runtime).reply_to_comment(username, text)
    if text.strip():
        record_notification_action(account_username, action="reply", actor_username=username,
                                   success=bool(result.get("success")), content=text)
    return {"type": "result", "command": "reply", **result}


def cmd_like(host: NotificationsHost, username: str, account_username: str = None) -> dict:
    """Like the comment / mention of ``username`` inline from the feed."""
    _watch_account_health(account_username)
    runtime = host.connect(False)
    result = _build_workflow(host, runtime).like_comment(username)
    record_notification_action(account_username, action="like", actor_username=username,
                               success=bool(result.get("success")))
    return {"type": "result", "command": "like", **result}


def cmd_follow_back(host: NotificationsHost, username: str, account_username: str = None) -> dict:
    """Follow ``username`` back inline from their "started following you" row."""
    _watch_account_health(account_username)
    runtime = host.connect(False)
    result = _build_workflow(host, runtime).follow_back(username)
    record_notification_action(account_username, action="follow_back", actor_username=username,
                               success=bool(result.get("success")))
    return {"type": "result", "command": "follow_back", **result}


def _batch_verbs(workflow, runtime) -> dict[str, Callable[[str, str], dict]]:
    """What each batch verb does with `(username, text)`: a tap on the feed, or a walk to a profile."""
    return {
        "like": lambda username, _text: workflow.like_comment(username),
        "reply": lambda username, text: workflow.reply_to_comment(username, text),
        "accept": lambda username, _text: workflow.accept_request(username),
        "ignore": lambda username, _text: workflow.ignore_request(username),
        "follow_back": lambda username, _text: workflow.follow_back(username),
        WELCOME_DM_ACTION: lambda username, text: send_welcome_dm(runtime.device, username, text),
        FOLLOW_ACTOR_ACTION: lambda username, _text: follow_actor(runtime.device, username),
    }


def cmd_batch(host: NotificationsHost, actions: list[dict], account_username: str = None,
              source: str = "batch", follow_back_daily_cap: int = None,
              welcome_dm_daily_cap: int = None, follow_actor_daily_cap: int = None) -> dict:
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

    Each action is ``{"action": "like"|"reply"|"accept"|"ignore"|"follow_back"|
    "welcome_dm"|"follow_actor", "username": str, "text": str?}`` plus an OPTIONAL identity
    ``notif_type`` / ``notif_text`` / ``notif_time`` (``text`` is already taken by the
    reply body, hence the prefix). When the identity is there, the entry's stable
    content_hash is computed and the action becomes IDEMPOTENT across scans: an action
    already recorded as succeeded for this account is skipped (``skipped: true`` in its
    result) instead of re-tapped — the autopilot's belt-and-braces above the scan's
    ``is_new``. Executed actions are recorded (audit + budget interactions), see
    ``record_notification_action``.

    ``welcome_dm`` sends the private message the app wrote for a brand-new follower, and
    ``follow_actor`` follows whoever engaged with one of OUR comments. Those two are the odd
    ones out: they leave the activity feed for a profile, so they are REORDERED to the end of
    the batch, paced between them, and each carries its own guards and dedicated daily cap.
    See welcome-dm-spec.md.

    One failing action does not abort the rest — a comment whose row scrolled out of reach must not
    cancel the nine others.
    """
    _watch_account_health(account_username)
    runtime = host.connect(False)
    workflow = _build_workflow(host, runtime)
    verbs = _batch_verbs(workflow, runtime)

    # Welcome DMs walk away from the activity feed, so they run after everything else.
    actions = order_batch_actions(actions)
    total = len(actions)
    results: list[dict] = []
    done = 0
    failed = 0
    skipped = 0
    # Preloaded once per verb present in the batch (no per-action DB hit).
    actioned_by_verb: dict[str, set] = {}
    # Dedicated daily caps (follow_back = autopilot tier 2, welcome_dm = the private
    # message): counted from the audit table ONCE per verb, then advanced locally as this
    # batch lands actions. Enforced HERE, not only front-side: the bot owns the audit
    # table, so the truth of "today" lives here. A verb with no cap passed is uncapped —
    # that is what an operator's manual selection is.
    daily_caps = {verb: cap for verb, cap in (("follow_back", follow_back_daily_cap),
                                              (WELCOME_DM_ACTION, welcome_dm_daily_cap),
                                              (FOLLOW_ACTOR_ACTION, follow_actor_daily_cap))
                  if cap is not None}
    used_today = {verb: count_actions_today(account_username, verb) for verb in daily_caps}
    # Resolved once, only when the batch actually carries a welcome DM: without it nothing
    # could be recorded, and the same message would be re-sent at every scan.
    welcome_account_id = (resolve_account_id(account_username or "")
                          if any((entry.get("action") or "").strip() == WELCOME_DM_ACTION
                                 for entry in actions) else None)

    for index, entry in enumerate(actions):
        action = (entry.get("action") or "").strip()
        username = (entry.get("username") or "").strip()
        text = entry.get("text") or ""
        identity = None
        if entry.get("notif_type") or entry.get("notif_text"):
            identity = {"ntype": entry.get("notif_type"), "actor": username,
                        "text": entry.get("notif_text"), "time": entry.get("notif_time")}
        entry_hash = batch_identity_hash(account_username, identity)

        def _skip(reason: str, why: str) -> None:
            """Record one entry as skipped and narrate it. A skip is a SUCCESS carrying a
            reason: nothing failed, a guard did its job."""
            results.append({"action": action, "username": username, "success": True,
                            "skipped": True, "reason": reason, "message": why})
            host.emit({
                "type": "notification_step", "step": "batch_result",
                "index": index, "total": total, "action": action,
                "username": username, "success": True,
                "message": f"[{index + 1}/{total}] {action} @{username} - {why}",
            })

        # The first refusal ends the batch: every entry left is reported, none is tapped.
        halt = run_halt.arret_demande()
        if halt:
            skipped += 1
            _skip(halt.get("code") or "halted", "batch stopped: "
                  + ("Instagram refuses actions (Try again later)"
                     if halt.get("code") == "action_blocked" else str(halt.get("code"))))
            continue

        cap = daily_caps.get(action)
        if cap is not None and used_today.get(action, 0) >= cap:
            skipped += 1
            _skip("daily_cap", f"daily {action} cap reached ({cap})")
            continue

        if action == WELCOME_DM_ACTION:
            # Guards a tap-a-row verb does not need: we are about to write to someone
            # privately, and a second welcome message is worse than none at all.
            welcome_skip = welcome_dm_skip_reason(welcome_account_id, username)
            if welcome_skip:
                skipped += 1
                _skip(welcome_skip, {
                    "no_account": "unknown account, nothing could be recorded",
                    "no_recipient": "no recipient",
                    "already_dmed": "already messaged",
                    "conversation_exists": "conversation already started",
                }.get(welcome_skip, welcome_skip))
                continue

        if entry_hash:
            if action not in actioned_by_verb:
                actioned_by_verb[action] = load_actioned_hashes(account_username, action)
            if entry_hash in actioned_by_verb[action]:
                skipped += 1
                _skip("already_done", "already done, skipped")
                continue

        host.emit({
            "type": "notification_step",
            "step": "batch_action",
            "index": index,
            "total": total,
            "action": action,
            "username": username,
            "message": f"[{index + 1}/{total}] {action} @{username}",
        })

        verb = verbs.get(action)
        try:
            result = (verb(username, text) if verb is not None
                      else {"success": False, "error": f"Unknown action: {action}"})
            # Every verb looks for the block after its own gesture (the one look).
            if (run_halt.arret_demande() or {}).get("code") == "action_blocked":
                result = {**result, "success": False, "stop_reason": "action_blocked"}
        except Exception as exc:  # noqa: BLE001
            # Isolated per action, on purpose: see the docstring.
            logger.error(f"[NOTIF] batch {action} @{username} failed: {exc}")
            result = {"success": False, "error": str(exc)}

        ok = bool(result.get("success"))
        # A verb can decide, once on screen, that there is nothing to do — `follow_actor`
        # reads the relationship and steps back. That is a skip, not a success: counting it
        # as done would inflate the run, and recording it would spend a slot of the cap on
        # an action that never happened.
        self_skipped = bool(result.get("skipped"))
        if self_skipped:
            skipped += 1
        else:
            done += 1 if ok else 0
            failed += 0 if ok else 1
        results.append({"action": action, "username": username, **result})

        # Bookkeeping: audit row (+ budget interaction on success) for every EXECUTED
        # action; a nothing-sent reply (empty text opens the UI only) records nothing.
        if not self_skipped and (action != "reply" or text.strip()):
            record_notification_action(
                account_username, action=action, actor_username=username,
                identity=identity, success=ok, source=source,
                content=text if action in ("reply", WELCOME_DM_ACTION) else None,
            )
            if ok and entry_hash:
                actioned_by_verb.setdefault(action, set()).add(entry_hash)
        if ok and not self_skipped and action in daily_caps:
            used_today[action] = used_today.get(action, 0) + 1
        if ok and not self_skipped and action == WELCOME_DM_ACTION:
            # The shared duplicate marker + the conversation itself, so the message shows
            # up in DM Responses and syncs to Turso like any other reply we sent.
            record_welcome_dm(welcome_account_id, username, text)

        host.emit({
            "type": "notification_step",
            "step": "batch_result",
            "index": index,
            "total": total,
            "action": action,
            "username": username,
            "success": ok,
            "message": f"[{index + 1}/{total}] {action} @{username} {'ok' if ok else 'failed'}",
        })

        if action in OFF_SCREEN_ACTIONS and not self_skipped:
            # Pace the actions that walk to a profile. The reordering guarantees they are
            # the tail of the batch, so "last entry" is "last of them". A self-skip walked
            # nowhere worth pausing for.
            wait_before_next_off_screen_action(is_last=index >= total - 1)

    halt = run_halt.arret_demande()
    return {
        "type": "result",
        "command": "batch",
        **({"stop_reason": halt.get("code")} if halt else {}),
        "success": failed == 0,
        "total": total,
        "done": done,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }


#: One row, one verb: the commands that act on the row of `username`.
ROW_ACTIONS = {
    "accept": cmd_accept,
    "ignore": cmd_ignore,
    "like": cmd_like,
    "follow_back": cmd_follow_back,
}


__all__ = [
    "NotificationsHost",
    "ROW_ACTIONS",
    "cmd_accept",
    "cmd_accept_all",
    "cmd_batch",
    "cmd_follow_back",
    "cmd_ignore",
    "cmd_like",
    "cmd_list_requests",
    "cmd_reply",
    "cmd_scan",
]
