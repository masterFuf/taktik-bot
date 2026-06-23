"""Notifications actions for Instagram compat diagnostics (Cartography Lab).

Atomic, single-shot probes for the modern Instagram "Notifications" surface and
its follow-requests sub-screen. Detection actions report a clear found/not-found
result; tap actions act on the FIRST matching element and report success.

Every UI signature comes from the centralized ``NOTIFICATION_SELECTORS`` catalog
(``social_media/instagram/ui/selectors/surfaces/notifications.py``) — no hardcoded
resource-id / text / content-desc lives here.
"""

import re
import time

from lxml import etree
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


# =============================================================================
# Read-only classifier — the engagement workflow's "read" backbone
# =============================================================================

# Time tokens like "54m", "10 h", "2 j", "1w", "3 d" trailing a row.
_TIME_RE = re.compile(r"\b(\d+\s*(?:min|mois|sem|[smhjdwy]))\b", re.IGNORECASE)
# Inline action affordances that mark a row as actionable (FR + EN).
_ACTION_WORDS = ("confirmer", "confirm", "répondre", "repondre", "reply",
                 "follow back", "se réabonner", "message", "supprimer", "remove")


def _classify_row(full: str, fragments) -> "tuple[str, str]":
    """Return (type, username) for a row's concatenated text.

    Username is the text BEFORE the matched type phrase (where the actor leads,
    e.g. "<user> a commencé à vous suivre"); for `message`/`shared` the phrase
    leads, so we fall back to the token AFTER it. Best-effort — the Lab cares
    most about the type + counts.
    """
    low = full.lower()
    for type_name, frags in fragments.items():
        for frag in frags:
            if not frag:
                continue
            idx = low.find(frag.lower())
            if idx == -1:
                continue
            if idx > 0:
                user = full[:idx]
            else:
                # Phrase leads (message/shared "... from <user>"): take what follows.
                after = full[idx + len(frag):]
                user = after.split(".")[0]
            user = _TIME_RE.sub("", user).strip(" :·-—· ")
            return type_name, user
    return "other", ""


def _row_has_action(text_low: str) -> bool:
    return any(w in text_low for w in _ACTION_WORDS)


@action("notifications.scan")
def scan(a, p):
    """READ-ONLY: classify every notification on the activity screen by type +
    metadata (username, time, snippet, has_action). Backbone of the engagement
    workflow's read pass. Scans the currently visible screen (no scroll, no
    side effects)."""
    fragments = N.classifier_fragments  # ordered dict type -> [FR+EN fragments]
    items: list = []
    seen: set = set()

    xml = a.device.get_xml_dump()
    if not xml:
        return {"success": False, "count": 0, "by_type": {}, "items": [],
                "message": "notifications.scan: empty XML dump (not on the notifications screen?)"}
    try:
        root = etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    except Exception as exc:
        logger.error(f"notifications.scan: XML parse failed: {exc}")
        return {"success": False, "count": 0, "by_type": {}, "items": [],
                "message": f"notifications.scan: XML parse failed: {str(exc)[:120]}"}

    for row in root.xpath('//node[contains(@resource-id, "activity_feed_newsfeed_story_row")]'):
        parts: list = []
        for node in row.iter():
            for attr in ("text", "content-desc"):
                val = node.get(attr)
                if val and val.strip():
                    parts.append(val.strip())
        full = " ".join(dict.fromkeys(parts)).strip()  # join, drop exact dupes, keep order
        if not full:
            continue
        key = full.lower()
        if key in seen:
            continue
        seen.add(key)
        ntype, username = _classify_row(full, fragments)
        time_match = _TIME_RE.findall(full)
        ts = time_match[-1].strip() if time_match else ""
        items.append({
            "type": ntype,
            "username": username,
            "time": ts,
            "text": full[:200],
            "has_action": _row_has_action(key),
        })

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

def _workflow(a):
    from taktik.core.social_media.instagram.workflows.management.notifications.notifications_workflow import (
        NotificationsEngagementWorkflow,
    )
    device_id = getattr(a.device, "device_id", None) or "lab"
    return NotificationsEngagementWorkflow(a.device, device_id)


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
