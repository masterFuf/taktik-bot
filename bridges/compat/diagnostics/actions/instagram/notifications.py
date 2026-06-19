"""Notifications actions for Instagram compat diagnostics (Cartography Lab).

Atomic, single-shot probes for the modern Instagram "Notifications" surface and
its follow-requests sub-screen. Detection actions report a clear found/not-found
result; tap actions act on the FIRST matching element and report success.

Every UI signature comes from the centralized ``NOTIFICATION_SELECTORS`` catalog
(``social_media/instagram/ui/selectors/surfaces/notifications.py``) — no hardcoded
resource-id / text / content-desc lives here.
"""

import time

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action
from taktik.core.social_media.instagram.ui.selectors import NOTIFICATION_SELECTORS as N


# =============================================================================
# Local helpers (selector-list aware; no hardcoded UI strings)
# =============================================================================

def _any_present(a, selectors) -> bool:
    """True if ANY selector in ``selectors`` matches a node in the current screen
    (single XML dump, fast)."""
    result = a.device.batch_xpath_check({"probe": list(selectors)})
    return bool(result.get("probe"))

def _detect(a, selectors, label):
    """Detection result dict for a screen/element described by a selector list."""
    found = _any_present(a, selectors)
    logger.info(f"{label}: {'found' if found else 'not found'}")
    return {"success": True, "found": found, "message": f"{label}: {'found' if found else 'not found'}"}

def _tap_first(a, selectors, label):
    """Tap the FIRST element matching any selector in ``selectors`` (human tap on
    its real bounds) and report success."""
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
# Navigation
# =============================================================================

@action("navigation.go_notifications")
def go_notifications(a, p):
    """Open the notifications screen by tapping the activity/heart entry."""
    result = _tap_first(a, N.activity_entry, "navigation.go_notifications")
    if result.get("success"):
        time.sleep(1.0)
    return result


# =============================================================================
# Detection
# =============================================================================

@action("notifications.is_open")
def is_open(a, p):
    """Is the notifications screen shown? (action_bar_title Notifications + activity_feed_list)."""
    return _detect(a, N.notifications_screen_indicators, "notifications.is_open")


@action("notifications.is_follow_requests_open")
def is_follow_requests_open(a, p):
    """Is the follow-requests sub-screen shown? (title Discover people + accept resource-id)."""
    return _detect(a, N.follow_requests_screen_indicators, "notifications.is_follow_requests_open")


# =============================================================================
# Taps (act on the FIRST matching element)
# =============================================================================

@action("notifications.open_follow_requests")
def open_follow_requests(a, p):
    """Tap the grouped follow-requests header row to open the sub-screen."""
    result = _tap_first(a, N.follow_requests_header, "notifications.open_follow_requests")
    if result.get("success"):
        time.sleep(1.0)
    return result


@action("notifications.confirm_follow_request")
def confirm_follow_request(a, p):
    """On the follow-requests sub-screen, tap the FIRST accept button."""
    return _tap_first(a, N.request_accept_button, "notifications.confirm_follow_request")


@action("notifications.dismiss_follow_request")
def dismiss_follow_request(a, p):
    """On the follow-requests sub-screen, tap the FIRST ignore button."""
    return _tap_first(a, N.request_ignore_button, "notifications.dismiss_follow_request")


@action("notifications.confirm_inline_request")
def confirm_inline_request(a, p):
    """On the MAIN notifications screen, tap the FIRST inline Confirm button."""
    return _tap_first(a, N.inline_confirm_button, "notifications.confirm_inline_request")


@action("notifications.reply_mention")
def reply_mention(a, p):
    """On the MAIN notifications screen, tap the FIRST Reply button on a comment-mention row."""
    return _tap_first(a, N.reply_button, "notifications.reply_mention")


@action("notifications.open_filter")
def open_filter(a, p):
    """Tap the Filter button on the notifications screen."""
    return _tap_first(a, N.filter_button, "notifications.open_filter")
