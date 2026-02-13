"""Pure UI detection functions shared across scraping, discovery, and post_scraping workflows.

All functions take `device` and `logger` as parameters — no class dependency.
"""

from ...ui.selectors import POST_SELECTORS, POPUP_SELECTORS, DETECTION_SELECTORS


def is_reel_post(device, logger=None) -> bool:
    """Check if current post is a Reel."""
    for selector in POST_SELECTORS.reel_indicators:
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
    indicators = POST_SELECTORS.post_view_indicators + POST_SELECTORS.post_detail_indicators
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
