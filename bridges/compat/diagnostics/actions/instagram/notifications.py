"""Notifications actions for Instagram compat diagnostics.

Atomic, single-shot probes for the "Notifications" surface and its follow-requests
sub-screen, the full engagement-workflow methods, and the whole run by its launcher
(``notifications.run``). Every probe reuses a
primitive of ``NotificationsEngagementWorkflow``; ``open_filter`` and
``confirm_inline_request`` are plain selector probes, since the workflow does not
drive those affordances.

Every UI signature comes from the centralized ``NOTIFICATION_SELECTORS`` catalog.
"""

import time
from contextlib import contextmanager

from loguru import logger

from bridges.compat.diagnostics.runtime.action_test.action_bundle import (
    bundle_device_id,
    resolve_lab_account_id,
)

from bridges.compat.diagnostics.actions.instagram import action
from taktik.core.social_media.instagram.ui.selectors import NOTIFICATION_SELECTORS as N


# =============================================================================
# Production workflow access + small shared helpers
# =============================================================================

def _workflow(a, p=None):
    """Build the production NotificationsEngagementWorkflow on the warm device.

    No notifier / relauncher: narration and self-heal are no-ops for an isolated
    probe. ``p`` attaches the per-profile pipeline, the same object the bridge
    injects.
    """
    from taktik.core.social_media.instagram.workflows.management.notifications.notifications_workflow import (
        NotificationsEngagementWorkflow,
    )
    device_id = getattr(a.device, "device_id", None) or "lab"
    return NotificationsEngagementWorkflow(
        a.device, device_id, profile_pipeline=_pipeline(a, p) if p is not None else None,
    )


def _pipeline(a, p, session_id=None):
    """Per-profile pipeline bound to the ``account`` param and a session.

    ``session_id`` is what attaches each follow to a session; without it the
    interactions belong to nothing and never surface in the history.
    """
    from taktik.core.social_media.instagram.workflows.management.notifications import (
        build_notifications_profile_pipeline,
    )
    return build_notifications_profile_pipeline(
        a.device, account_id=resolve_lab_account_id(p), session_id=session_id,
    )


@contextmanager
def lab_suggestion_session(p, source):
    """A real automation session around a diagnostics run.

    One session per trigger, carrying its ``stats_*`` snapshot once the run ends.
    Without an account no session is opened, so the work is never attributed to
    someone else.
    """
    from taktik.core.social_media.instagram.actions.business.workflows.common.suggestion_session import (
        suggestion_session,
    )
    account_id = resolve_lab_account_id(p)
    if not account_id:
        logger.warning(f"No 'account' parameter given — "
                       f"the {source} run will not be attached to any session")
    with suggestion_session(account_id, source=f"lab:{source}") as session_id:
        yield session_id


def _detected(label, found):
    """Detection result dict for a screen described by a prod predicate."""
    logger.info(f"{label}: {'found' if found else 'not found'}")
    return {"success": True, "found": found,
            "message": f"{label}: {'found' if found else 'not found'}"}


def _tap_first(a, selectors, label):
    """Tap the FIRST element matching any selector, through the production finder.

    Used only by the probes the workflow does not drive. Delegates to
    ``_find_and_click`` so the ordered search, the humanized tap and the selector
    tracing are the production ones.
    """
    ok = a.click._find_and_click(list(selectors), timeout=2)
    if ok:
        logger.info(f"{label}: tapped")
        return {"success": True, "message": f"{label}: tapped"}
    logger.warning(f"{label}: no matching element")
    return {"success": False, "message": f"{label}: no matching element"}


# =============================================================================
# Navigation  (prod: NotificationsEngagementWorkflow._tap_activity_and_check)
# =============================================================================

@action("navigation.go_notifications")
def go_notifications(a, p):
    """Open the notifications screen by tapping the activity/heart entry.

    Reuses the prod ``_tap_activity_and_check`` (tap the activity entry, then
    verify the notifications screen is shown)."""
    ok = _workflow(a)._tap_activity_and_check()
    msg = ("navigation.go_notifications: notifications screen opened" if ok
           else "navigation.go_notifications: notifications screen not reached")
    (logger.info if ok else logger.warning)(msg)
    return {"success": ok, "message": msg}


# =============================================================================
# Detection  (prod: _on_notifications_screen / _on_follow_requests_screen)
# =============================================================================

@action("notifications.is_open")
def is_open(a, p):
    """Is the notifications screen shown? (prod ``_on_notifications_screen``)."""
    return _detected("notifications.is_open", _workflow(a)._on_notifications_screen())


@action("notifications.is_follow_requests_open")
def is_follow_requests_open(a, p):
    """Is the follow-requests sub-screen shown? (prod ``_on_follow_requests_screen``)."""
    return _detected("notifications.is_follow_requests_open",
                     _workflow(a)._on_follow_requests_screen())


# =============================================================================
# Taps  (reuse prod primitives)
# =============================================================================

@action("notifications.open_follow_requests")
def open_follow_requests(a, p):
    """Open the follow-requests sub-screen via the prod ``_open_grouped_requests``.

    Taps the grouped digest row's LEFT avatar cluster — the reliable hit target;
    a center tap on the row text is flaky even by hand (this is exactly why prod
    targets the avatar zone, and why the Lab must drive the same code)."""
    ok = _workflow(a)._open_grouped_requests()
    if ok:
        time.sleep(1.0)
    msg = ("notifications.open_follow_requests: opened" if ok
           else "notifications.open_follow_requests: grouped header not found")
    (logger.info if ok else logger.warning)(msg)
    return {"success": ok, "message": msg}


def _act_first_request(a, which, label):
    """Confirm (``which='accept'``) or ignore (``which='ignore'``) the FIRST pending
    request on the sub-screen, reusing the prod row parser + humanized tap."""
    wf = _workflow(a)
    rows = wf._request_rows()
    row = next((r for r in rows if r.get(which)), None)
    if not row:
        logger.warning(f"{label}: no pending request in view")
        return {"success": False, "message": f"{label}: no pending request in view"}
    username = row.get("username", "")
    if not wf._tap_point(row[which], f"{label} {username}".strip()):
        return {"success": False, "message": f"{label}: tap failed"}
    msg = f"{label}: {which} {username}".strip()
    logger.info(msg)
    return {"success": True, "message": msg}


@action("notifications.confirm_follow_request")
def confirm_follow_request(a, p):
    """On the follow-requests sub-screen, confirm the FIRST pending request.

    Reuses the prod request-row parser + humanized tap (``_request_rows`` +
    ``_tap_point``) instead of a blind selector tap, so the Lab exercises the same
    row geometry the engagement workflow uses."""
    return _act_first_request(a, "accept", "notifications.confirm_follow_request")


@action("notifications.dismiss_follow_request")
def dismiss_follow_request(a, p):
    """On the follow-requests sub-screen, ignore/delete the FIRST pending request
    (prod ``_request_rows`` + ``_tap_point``)."""
    return _act_first_request(a, "ignore", "notifications.dismiss_follow_request")


@action("notifications.confirm_inline_request")
def confirm_inline_request(a, p):
    """On the MAIN notifications screen, tap the FIRST inline Confirm button.

    Selector probe: the production engagement workflow handles follow requests via
    the sub-screen, not the inline main-feed Confirm affordance, so there is no
    workflow primitive to reuse here."""
    return _tap_first(a, N.inline_confirm_button, "notifications.confirm_inline_request")


@action("notifications.reply_mention")
def reply_mention(a, p):
    """On the MAIN notifications screen, open the reply UI on the FIRST mention.

    Reuses the prod ``_open_reply_thread('')`` (taps the first Reply affordance on
    screen, bounds-paired, humanized)."""
    ok = _workflow(a)._open_reply_thread("")
    msg = ("notifications.reply_mention: reply opened" if ok
           else "notifications.reply_mention: no reply affordance on screen")
    (logger.info if ok else logger.warning)(msg)
    return {"success": ok, "message": msg}


@action("notifications.open_filter")
def open_filter(a, p):
    """Tap the Filter button on the notifications screen.

    Selector probe: the production workflow does not drive the activity filter, so
    there is no workflow primitive to reuse here."""
    return _tap_first(a, N.filter_button, "notifications.open_filter")


# =============================================================================
# Read-only classifier — prod read backbone on a SINGLE screen
# =============================================================================

@action("notifications.scan")
def scan(a, p):
    """READ-ONLY: classify every notification on the CURRENT activity screen by
    type + metadata (username, time, label, has_action). No scroll, no side effects.

    Reuses the prod ``_dump_screen`` (real ``parse_feed_rows`` + ``classifier``) so
    the Lab tests the exact classification the engagement workflow's read pass uses
    (vs the full-scroll ``notifications.scan_full``)."""
    rows, _headers = _workflow(a)._dump_screen()
    items = [{
        "type": r.get("type", "other"),
        "username": r.get("username", ""),
        "time": r.get("time", ""),
        "text": (r.get("text") or "")[:200],
        "label": r.get("label", ""),
        "has_action": bool(r.get("has_action")),
    } for r in rows]
    by_type: dict = {}
    for it in items:
        by_type[it["type"]] = by_type.get(it["type"], 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())) or "none"
    msg = f"notifications.scan: {len(items)} notifications [{summary}]"
    logger.info(msg)
    return {"success": True, "count": len(items), "by_type": by_type, "items": items, "message": msg}


# =============================================================================
# Engagement workflow — REAL methods (scroll, username-targeting, OCR, click-in).
# Each builds the production NotificationsEngagementWorkflow on the warm device
# (no notifier/relauncher: narration + self-heal are no-ops for an isolated unit).
# =============================================================================

@action("notifications.scan_full")
def scan_full(a, p):
    """FULL engagement read: scroll + 'Show more' + OCR-expand truncated rows +
    emoji recovery + follow-requests collection (vs the read-only notifications.scan
    probe). Param: max_scrolls (int, default 3). The workflow self-navigates."""
    max_scrolls = int(p.get("max_scrolls") or 3)
    return _workflow(a).scan(max_scrolls=max_scrolls)


@action("notifications.list_requests")
def list_requests(a, p):
    """Enumerate pending follow-request usernames on the sub-screen (progressive-render
    polling + scroll). Param: max_requests (int, default 50)."""
    max_requests = int(p.get("max_requests") or 50)
    return _workflow(a).list_requests(max_requests=max_requests)


@action("notifications.accept_request")
def accept_request(a, p):
    """Confirm ONE follow request BY USERNAME (row-targeted, scrolls to find it).
    Param: username (required)."""
    username = (p.get("username") or "").strip()
    if not username:
        return {"success": False, "message": "username param is required"}
    return _workflow(a).accept_request(username)


@action("notifications.ignore_request")
def ignore_request(a, p):
    """Delete ONE follow request BY USERNAME (row-targeted). Param: username (required)."""
    username = (p.get("username") or "").strip()
    if not username:
        return {"success": False, "message": "username param is required"}
    return _workflow(a).ignore_request(username)


@action("notifications.accept_all_requests")
def accept_all_requests(a, p):
    """Batch-confirm pending follow requests (top-of-list, re-read between taps).
    Param: max_requests (int, default 50)."""
    max_requests = int(p.get("max_requests") or 50)
    return _workflow(a).accept_all_requests(max_requests=max_requests)


@action("notifications.like_comment")
def like_comment(a, p):
    """Tap the inline 'Like' on the comment/mention row of ``username`` (scrolls to
    reveal it). Param: username (optional → likes the first likeable row)."""
    return _workflow(a).like_comment((p.get("username") or "").strip())


@action("notifications.follow_back")
def follow_back(a, p):
    """Tap the inline 'Follow back' on the new-follower row of ``username`` (scrolls to
    reveal it). Param: username (optional → follows back the first row with the button).
    Exact-label match: an already-followed row reads as "no button", never an unfollow."""
    return _workflow(a).follow_back((p.get("username") or "").strip())


@action("notifications.open_mention")
def open_mention(a, p):
    """Open the comment thread of ``username``'s row WITHOUT typing (row-scoped).
    Param: username (optional → first reply affordance)."""
    return _workflow(a).open_mention((p.get("username") or "").strip())


@action("notifications.reply_to_comment")
def reply_to_comment(a, p):
    """Full reply: click-in the row → type → send → back. Params: username, text
    (empty text → just opens the reply UI)."""
    return _workflow(a).reply_to_comment((p.get("username") or "").strip(), (p.get("text") or "").strip())


@action("notifications.expand_more")
def expand_more(a, p):
    """Expand ONE truncated comment/mention row in view via OCR ('… more'/'… suite').
    Device must be on the notifications screen with a truncated row visible."""
    wf = _workflow(a)
    wf._expanded_keys = set()
    tried = wf._expand_one_more()
    return {"success": bool(tried),
            "message": "expanded a truncated row" if tried else "no truncated row in view (or OCR unavailable)"}


# =============================================================================
# Suggestions (bottom of the notifications screen)
# =============================================================================

@action("notifications.scan_suggestions")
def scan_suggestions(a, p):
    """Read the "Suggestions" zone at the bottom of the notifications screen.

    The row and its button carry a resource-id; the fields inside do not. The button
    state is read by the same function as the profile header. Scroll to the bottom of
    the screen before running this probe.
    """
    rows = _workflow(a).scan_suggestions()
    if not rows:
        return {"success": False, "found": False,
                "message": "Aucune suggestion lue (en-tete hors ecran ?)"}
    by_state = {}
    for row in rows:
        key = row.get("state") or "illisible"
        by_state[key] = by_state.get(key, 0) + 1
    summary = ", ".join(f"{count} {state}" for state, count in sorted(by_state.items()))
    return {"success": True, "found": True,
            "message": f"{len(rows)} suggestion(s): {summary}",
            "details": {"rows": rows, "by_state": by_state}}


@action("notifications.reach_suggestions")
def reach_suggestions(a, p):
    """Descendre jusqu'a l'en-tete "Suggestions" (param ``max_scrolls``, 60 par defaut).

    The zone sits at the very bottom of the screen: without this descent, every probe
    that follows reads a screen where the zone simply is not there. The descent stops on
    PROGRESS — two identical screens mean the bottom — and ``max_scrolls`` is only an
    anti-loop guard.
    """
    max_scrolls = int(p.get("max_scrolls", 60))
    ok = _workflow(a).reach_suggestions_zone(max_scrolls=max_scrolls)
    msg = ("notifications.reach_suggestions: zone suggestions atteinte" if ok
           else f"notifications.reach_suggestions: en-tete jamais vu apres {max_scrolls} scroll(s)")
    (logger.info if ok else logger.warning)(msg)
    return {"success": ok, "found": ok, "message": msg}


@action("notifications.open_suggestion_profile")
def open_suggestion_profile(a, p):
    """Open the PROFILE of the first followable suggestion, and prove it.

    Taps the row body, never its button, then requires proof of the profile surface.
    That is what separates this mode from a blind follow: without the profile there
    is only the display label and never the @handle.

    ``account`` (optional): account the follow-up is attributed to. This probe writes
    nothing — it opens, it does not follow — so it opens no session.
    """
    wf = _workflow(a, p)
    rows = wf.scan_suggestions()
    from taktik.core.social_media.instagram.workflows.management.notifications.suggestions_parsing import (
        followable_suggestions,
    )
    candidates = followable_suggestions(rows)
    if not candidates:
        msg = "notifications.open_suggestion_profile: aucune suggestion suivable a l'ecran"
        logger.warning(msg)
        return {"success": False, "message": msg}
    row = candidates[0]
    label = row.get("label") or "?"
    ok = wf.open_suggestion_profile(row)
    if not ok:
        return {"success": False,
                "message": f"notifications.open_suggestion_profile: '{label}' n'a pas ouvert de profil"}
    username = wf.profile_pipeline.read_username()
    return {"success": True,
            "message": f"notifications.open_suggestion_profile: '{label}' -> @{username or '?'}",
            "details": {"label": label, "username": username}}


@action("notifications.qualify_suggestion_profile")
def qualify_suggestion_profile(a, p):
    """Run the per-profile pipeline on the profile ALREADY open on screen.

    Extraction, AI qualification when a service is wired, filters, follow and DB
    writes — the same function the target and hashtag runs use.

    Params: ``account`` (attribution), ``username`` (forces the handle when the
    on-screen read fails).
    """
    with lab_suggestion_session(p, "qualify_profile") as session_id:
        pipeline = _pipeline(a, p, session_id)
        if not pipeline.wait_for_profile(timeout=float(p.get("timeout", 8))):
            msg = "notifications.qualify_suggestion_profile: l'ecran courant n'est pas un profil"
            logger.warning(msg)
            return {"success": False, "message": msg}
        username = (p.get("username") or "").strip().lstrip("@") or pipeline.read_username()
        if not username:
            msg = "notifications.qualify_suggestion_profile: @handle illisible sur ce profil"
            logger.warning(msg)
            return {"success": False, "message": msg}
        outcome = pipeline.process(username)
        return {"success": not outcome.was_error,
                "message": (f"notifications.qualify_suggestion_profile: @{username} -> "
                            f"{outcome.status} ({outcome.follows} follow) "
                            f"[session {session_id or 'aucune'}]"),
                "details": {"username": username, "status": outcome.status,
                            "follows": outcome.follows, "session_id": session_id,
                            "reasons": list(outcome.filter_reasons or [])}}


@action("notifications.leave_suggestion_profile")
def leave_suggestion_profile(a, p):
    """Go back from the profile to the notifications screen (bounded backs + self-heal)."""
    ok = _workflow(a).leave_suggestion_profile()
    msg = ("notifications.leave_suggestion_profile: retour aux notifications" if ok
           else "notifications.leave_suggestion_profile: ecran notifications non retrouve")
    (logger.info if ok else logger.warning)(msg)
    return {"success": ok, "message": msg}


# =============================================================================
# The whole run  (prod: run_instagram_notifications, the notifications bridge's launcher)
# =============================================================================

def _log_run_event(payload: dict) -> None:
    # The step and its narration only, never a message body.
    logger.info(f"notifications.run: {payload.get('step', payload.get('type', 'event'))} "
                f"{payload.get('step_status', '')} {payload.get('message', '')}".rstrip())


@action("notifications.run")
def run_notifications(a, p):
    """The whole notifications run, by `run_instagram_notifications`: the launcher the desktop's
    notifications bridge and the CLI call, on the session's phone.

    Params are the launcher's own keys: ``command`` (``scan`` by default, like the CLI handler;
    ``list_requests``, ``accept_all``, ``accept``, ``ignore``, ``like``, ``follow_back``,
    ``reply``), ``scroll`` and ``followSuggestions`` (scan), ``limit`` (list_requests), ``max``
    (accept_all), ``username`` and ``text`` (row verbs, reply), ``accountUsername``. A ``batch``
    needs a list of actions, which the Lab's fields cannot give: the reader refuses it. A scan
    restarts Instagram first and closes it at the end, as in production. The run's events come
    back in ``details.events``; stdout stays the session's.
    """
    from taktik.core.social_media.instagram.workflows.management.notifications import agent_handler

    device_id = bundle_device_id(a)
    if not device_id:
        msg = "notifications.run: no phone serial for this session, nothing run"
        logger.error(msg)
        return {"success": False, "message": msg}

    config = dict(p)
    config.setdefault("command", "scan")
    events: list = []

    def emit(payload: dict) -> None:
        events.append(payload)
        _log_run_event(payload)

    try:
        result = agent_handler.run_instagram_notifications(
            config,
            connect=lambda package_name, restart: _connected_runtime(a, device_id, package_name, restart),
            emit=emit,
            # The app never sends an `ai` block, and the bridge's AI service prints on stdout.
            instagram_ai_service=None,
        )
    except agent_handler.NotificationsCommandError as exc:
        msg = f"notifications.run: refused before the phone: {exc}"
        logger.warning(msg)
        return {"success": False, "message": msg, "details": {"events": events}}

    success = bool(result.get("success"))
    msg = f"notifications.run {config['command']}: {result.get('message') or ('done' if success else 'failed')}"
    (logger.info if success else logger.warning)(msg)
    return {"success": success, "message": msg, "details": {"result": result, "events": events}}


def _connected_runtime(a, device_id: str, package_name, restart: bool):
    """The desktop bridge's runtime (`NotificationsBridge`) on the phone the Lab session holds: the
    same clone-aware device and the same clean restart (`AppService`) as the bridge and the CLI,
    through the helper the CLI uses, without a second connection."""
    from types import SimpleNamespace

    from bridges.common.runtime.connected_device import on_connected_device
    from bridges.instagram.engagement.runtime.notifications.bridge import NotificationsBridge

    # The raw device under the session's facade: the bridge puts its own proxy and facade on it.
    raw = getattr(a.device, "_device", None) or a.device
    runtime = on_connected_device(NotificationsBridge(device_id, package_name=package_name),
                                  SimpleNamespace(device=raw), device_id)
    if restart:
        runtime.restart_instagram()
    return runtime


@action("notifications.visit_suggestions")
def visit_suggestions(a, p):
    """Boucle complete : descendre -> ouvrir -> qualifier -> follow -> revenir -> suivante.

    Params: ``max`` (profiles, 1 by default), ``max_descent_scrolls`` (descent guard),
    ``max_scrolls`` (scrolling INSIDE the zone), ``account``.
    """
    max_profiles = int(p.get("max", 1))
    with lab_suggestion_session(p, "notifications") as session_id:
        wf = _workflow(a, p)
        wf.profile_pipeline = _pipeline(a, p, session_id)
        res = wf.visit_suggestions(
            max_profiles=max_profiles,
            max_scrolls=int(p.get("max_scrolls", 8)),
            max_descent_scrolls=int(p.get("max_descent_scrolls", 60)),
            # A probe tests the zone on the screen the operator navigated to, so the
            # list is not collapsed here — production does the opposite.
            refresh_first=str(p.get("refresh_first", "")).lower() in ("1", "true", "oui"),
            delay_range=(float(p.get("delay_min", 2)), float(p.get("delay_max", 5))),
        )
    res["session_id"] = session_id
    return {"success": res.get("processed", 0) > 0,
            "message": (f"{res.get('visited', 0)}/{max_profiles} profil(s) visite(s), "
                        f"{res.get('follows', 0)} follow(s), "
                        f"{res.get('filtered', 0)} filtre(s), "
                        f"{res.get('errors', 0)} erreur(s), "
                        f"arret: {res.get('stop_reason')} "
                        f"[session {session_id or 'aucune'}]"),
            "details": res}
