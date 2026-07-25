"""Pure UI detection functions shared across scraping, discovery, and post_scraping workflows.

All functions take `device` and `logger` as parameters — no class dependency.
"""

import re
from typing import Any, Dict, List

from ...ui.selectors.shell.popups import POPUP_SELECTORS
from ...ui.selectors.surfaces.post import (
    POST_COMMENTS_SELECTORS,
    POST_DETAIL_SELECTORS,
    POST_REELS_SELECTORS,
)

# Labels that pass the username regex but are action buttons, not people.
_COMMENTER_ACTION_TEXTS = frozenset({
    'Reply', 'Hide', 'Like', 'Follow', 'Following', 'Remove',
    'Post', 'Translate', 'Report', 'Signaler', 'Retirer',
    'Répondre', 'Masquer', 'Suivre', 'Publier',
})
_COMMENTER_USERNAME_RE = re.compile(r'^[a-zA-Z0-9._]{1,30}$')
# The post card's counter buttons ("18.5K", "1,204", "428", "4") carry an empty content-desc
# and numeric text, so nothing in their attributes tells them apart from a username. Scoping
# the query to the comments list already removes them; this rejects them a second time in
# case the container cannot be resolved. An all-digit handle is legal on Instagram but
# vanishingly rare, and losing one costs a missed row — accepting one costs a mis-tap into
# the likers sheet, followed by a failed profile load.
_COUNTER_LIKE_TEXT_RE = re.compile(r'^[\d.,]+[KkMm]?$')


def is_reel_post(device, logger=None) -> bool:
    """Check if current post is a Reel."""
    for selector in POST_REELS_SELECTORS.reel_indicators:
        try:
            if device.xpath(selector).exists:
                if logger:
                    logger.debug(f"Reel detected via: {selector[:60]}")
                return True
        except Exception:
            continue
    return False


def is_in_post_view(device, logger=None) -> bool:
    """Check if we're currently viewing a post (not grid/profile)."""
    indicators = POST_DETAIL_SELECTORS.post_view_indicators + POST_DETAIL_SELECTORS.post_detail_indicators
    for indicator in indicators:
        try:
            if device.xpath(indicator).exists:
                if logger:
                    logger.debug(f"Post view detected via: {indicator[:60]}")
                return True
        except Exception:
            continue
    return False


def is_likers_popup_open(device, logger=None) -> bool:
    """Check if likers popup is open."""
    for selector in POPUP_SELECTORS.likers_popup_indicators:
        try:
            if device.xpath(selector).exists:
                return True
        except Exception:
            continue
    return False


def is_comments_view_open(device, logger=None) -> bool:
    """Check if comments view is open."""
    for selector in POPUP_SELECTORS.comments_view_indicators:
        try:
            if device.xpath(selector).exists:
                return True
        except Exception:
            continue
    return False


def read_visible_commenters(device, logger=None) -> List[Dict[str, Any]]:
    """Read the people visible in the comments thread, as {'username', 'element'} rows.

    A commenter's username is an `android.widget.Button` whose @content-desc is EMPTY; the
    action buttons around it (Reply / Like / See translation) carry their visible label as
    @content-desc. That discriminator is the only thing separating the two, so it lives here
    once — both the scraping loop and the interaction loop read commenters this way.

    Scoped to the comments list, because the post card underneath the sheet exposes counter
    buttons that are shaped exactly like a username node. Falls back to the whole screen if
    the container cannot be resolved, so a renamed RecyclerView degrades to the previous
    (over-broad) behaviour rather than to reading nothing.
    """
    buttons = None
    for selector in (POST_COMMENTS_SELECTORS.commenter_button_nodes_in_list_selector,
                     POST_COMMENTS_SELECTORS.commenter_button_nodes_selector):
        try:
            buttons = device.xpath(selector).all()
        except Exception as exc:
            if logger:
                logger.debug(f"[commenters] xpath dump failed: {exc}")
            return []
        if buttons:
            break

    rows: List[Dict[str, Any]] = []
    for elem in buttons or []:
        try:
            text = (elem.text or '').strip().lstrip('@')
            if elem.attrib.get('content-desc', None) != '':
                continue
            if not text or not _COMMENTER_USERNAME_RE.match(text):
                continue
            if text in _COMMENTER_ACTION_TEXTS or _COUNTER_LIKE_TEXT_RE.match(text):
                continue
            rows.append({'username': text, 'element': elem})
        except Exception:
            continue
    return rows
