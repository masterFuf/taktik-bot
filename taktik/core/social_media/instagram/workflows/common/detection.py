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
    """
    try:
        buttons = device.xpath(POST_COMMENTS_SELECTORS.commenter_button_nodes_selector).all()
    except Exception as exc:
        if logger:
            logger.debug(f"[commenters] xpath dump failed: {exc}")
        return []

    rows: List[Dict[str, Any]] = []
    for elem in buttons:
        try:
            text = (elem.text or '').strip().lstrip('@')
            if elem.attrib.get('content-desc', None) != '':
                continue
            if not text or not _COMMENTER_USERNAME_RE.match(text):
                continue
            if text in _COMMENTER_ACTION_TEXTS:
                continue
            rows.append({'username': text, 'element': elem})
        except Exception:
            continue
    return rows
