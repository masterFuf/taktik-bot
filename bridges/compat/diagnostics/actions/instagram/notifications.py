"""Notifications actions for Instagram compat diagnostics (Cartography Lab).

Atomic, single-shot probes for the modern Instagram "Notifications" surface and
its follow-requests sub-screen, PLUS the full engagement-workflow methods.

PROD-ALIGNED: every probe reuses a primitive of the production
``NotificationsEngagementWorkflow`` (navigation / detection / dump parsing /
humanized tap) — there is no Lab-only re-implementation of screen detection or
notification classification. So a green Lab run exercises the exact code the real
engagement workflow runs. The only exceptions are ``open_filter`` and
``confirm_inline_request``: the production workflow does not (yet) drive those UI
affordances, so they stay as plain selector probes of the centralized catalog.

Every UI signature comes from the centralized ``NOTIFICATION_SELECTORS`` catalog
(``social_media/instagram/ui/selectors/surfaces/notifications.py``) — no hardcoded
resource-id / text / content-desc lives here.
"""

import time

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action
from taktik.core.social_media.instagram.ui.selectors import NOTIFICATION_SELECTORS as N


# =============================================================================
# Production workflow access + small shared helpers
# =============================================================================

def _workflow(a):
    """Build the production NotificationsEngagementWorkflow on the warm Lab device.

    No notifier / relauncher: narration + self-heal are no-ops for an isolated
    unit probe. The Lab session already optimized the selector catalog to the
    device language at start, so the workflow's text-only signatures (e.g. the
    grouped follow-requests header) resolve without re-detecting per action.
    """
    from taktik.core.social_media.instagram.workflows.management.notifications.notifications_workflow import (
        NotificationsEngagementWorkflow,
    )
    device_id = getattr(a.device, "device_id", None) or "lab"
    return NotificationsEngagementWorkflow(a.device, device_id)


def _detected(label, found):
    """Detection result dict for a screen described by a prod predicate."""
    logger.info(f"{label}: {'found' if found else 'not found'}")
    return {"success": True, "found": found,
            "message": f"{label}: {'found' if found else 'not found'}"}


def _tap_first(a, selectors, label):
    """Tap the FIRST element matching any selector (human tap on its real bounds).

    Used only by the probes the production workflow does not drive
    (``open_filter`` / ``confirm_inline_request``); every other probe reuses a
    workflow primitive.
    """
    for selector in selectors:
        try:
            element = a.device.xpath(selector).get(timeout=2.0)
        except Exception:
            continue
        if not element:
            continue
        try:
            bounds = tuple(element.bounds)
        except Exception:
            bounds = None
        if bounds:
            point = a.device.human_tap(bounds)
            if point:
                logger.info(f"{label}: tapped @ {point}")
                return {"success": True, "message": f"{label}: tapped @ {point}"}
        # Fallback: click the element directly when bounds are unavailable.
        try:
            element.click()
            logger.info(f"{label}: clicked element")
            return {"success": True, "message": f"{label}: clicked element"}
        except Exception as exc:
            logger.error(f"{label}: click failed: {exc}")
            return {"success": False, "message": f"{label}: click failed: {str(exc)[:120]}"}
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
# Each builds the production NotificationsEngagementWorkflow on the warm Lab device
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
