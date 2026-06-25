"""Shared post navigation functions for scraping/discovery workflows.

All functions take `device` and `logger` as parameters — no class dependency.
"""

import time
from typing import Optional

from ...ui.selectors.shell.screen_state import DETECTION_SELECTORS
from ...ui.selectors.surfaces.post.grid import POST_GRID_SELECTORS
from ...ui.selectors.surfaces.post.likers import POST_LIKERS_SELECTORS
from ...ui.selectors.surfaces.post.share_sheet import POST_SHARE_SHEET_SELECTORS
from taktik.core.shared.behavior.gesture_primitives import human_scroll_raw
from .detection import is_in_post_view, is_likers_popup_open


def open_first_post_of_profile(device, logger=None) -> bool:
    """Open the first post in the current profile's grid."""
    try:
        posts = device.xpath(DETECTION_SELECTORS.post_thumbnail_selectors[0]).all()

        if not posts:
            posts = device.xpath(POST_GRID_SELECTORS.first_post_grid).all()

        if not posts:
            if logger:
                logger.error("No posts found in grid")
            return False

        posts[0].click()
        time.sleep(3)

        if is_in_post_view(device, logger):
            if logger:
                logger.info("First post opened successfully")
            return True

        if logger:
            logger.error("Failed to open first post")
        return False

    except Exception as e:
        if logger:
            logger.error(f"Error opening first post: {e}")
        return False


def open_likers_list(device, ui_extractors, logger=None) -> bool:
    """Open the likers list from the current post view.

    Strategy 1 (most reliable): click the "Liked by" / "Aimé par" text that
    appears below the post image.  Click the left side of the element to land
    on "Liked by", not on the first username (which would navigate to a profile).

    Strategy 2 (fallback): click the numeric like-count button detected by
    find_like_count_element().

    Args:
        device: uiautomator2 device
        ui_extractors: InstagramUIExtractors instance (has find_like_count_element)
        logger: optional logger
    """
    try:
        clicked = False

        # ── Strategy 1: "Liked by" / "Aimé par" text ──────────────────────────
        for selector in POST_LIKERS_SELECTORS.liked_by_selectors:
            try:
                element = device.xpath(selector)
                if element.exists:
                    info = element.info
                    bounds = info.get('bounds', {})
                    if bounds:
                        # Click ~40px from the left edge to hit "Liked by", not the username
                        left = bounds.get('left', 0)
                        top = bounds.get('top', 0)
                        bottom = bounds.get('bottom', 0)
                        click_x = left + 40
                        click_y = (top + bottom) // 2
                        device.click(click_x, click_y)
                    else:
                        element.click()
                    clicked = True
                    if logger:
                        logger.debug(f"Clicked 'Liked by' text via {selector}")
                    break
            except Exception:
                continue

        # ── Strategy 2: numeric like-count button (fallback) ──────────────────
        if not clicked:
            like_count_element = ui_extractors.find_like_count_element(logger_instance=logger)
            if like_count_element:
                like_count_element.click()
                clicked = True
                if logger:
                    logger.debug("Clicked like-count element")
            else:
                if logger:
                    logger.warning("No like counter found (tried 'Liked by' text and numeric button)")
                return False

        time.sleep(2.0)

        if is_likers_popup_open(device, logger):
            if logger:
                logger.debug("Likers popup opened successfully")
            return True

        if logger:
            logger.warning("Could not verify likers popup opened after click")
        return False

    except Exception as e:
        if logger:
            logger.error(f"Error opening likers list: {e}")
        return False


def get_post_url_from_share(device, logger=None) -> Optional[str]:
    """Extract the Instagram URL of the currently open post via the Share button.

    Flow:
      1. Tap the Share button on the post.
      2. In Instagram's share sheet, tap "Copy link".
      3. On devices where tapping "Copy link" opens the Android system share
         picker (e.g. Samsung Quick Share), the URL is visible as a text
         element — we read it directly without clipboard access.
      4. Close any remaining sheets and return the URL.

    Args:
        device: uiautomator2 device
        logger: optional logger

    Returns:
        The full Instagram post URL, or None if it could not be retrieved.
    """
    try:
        # Step 1: tap the share button.
        # Different post types use different resource-ids / content-desc:
        #   - Reels: direct_share_button
        #   - Regular feed posts: row_feed_button_share / "Send Post"
        # Selectors are centralised in POST_SHARE_SHEET_SELECTORS.share_button_selectors and use
        # contains(@resource-id) so they work with clone APKs.
        share_btn = None
        for sel in POST_SHARE_SHEET_SELECTORS.share_button_selectors:
            elem = device.xpath(sel)
            if elem.exists:
                share_btn = elem
                break

        if share_btn is None:
            if logger:
                logger.debug("get_post_url_from_share: share button not found")
            return None

        share_btn.click()
        time.sleep(1.5)

        # Step 2: tap "Copy link" in Instagram's share sheet.
        # Try the visible area first; if not found, scroll down to reveal the
        # action row that may be hidden below the DM recipients grid.
        copy_link = None
        for sel in POST_SHARE_SHEET_SELECTORS.copy_link_selectors:
            elem = device.xpath(sel)
            if elem.exists:
                copy_link = elem
                break

        if copy_link is None:
            # "Copy link" may be below the recipient grid — reveal it with a small humanized
            # scroll (was a hardcoded-coordinate swipe `288,900 -> 288,600`).
            human_scroll_raw(device, "down", distance_ratio=0.2)
            time.sleep(0.5)
            for sel in POST_SHARE_SHEET_SELECTORS.copy_link_selectors:
                elem = device.xpath(sel)
                if elem.exists:
                    copy_link = elem
                    break

        if copy_link is None:
            if logger:
                logger.debug("get_post_url_from_share: 'Copy link' not found in share sheet (tried scroll)")
            device.press("back")
            time.sleep(0.5)
            return None

        copy_link.click()
        time.sleep(1.0)

        # Step 3: read URL from system share picker (visible as text element)
        url = None
        for url_sel in POST_SHARE_SHEET_SELECTORS.share_picker_url_selectors:
            url_elem = device.xpath(url_sel)
            if url_elem.exists:
                url = url_elem.get_text().strip()
                if logger:
                    logger.debug(f"get_post_url_from_share: URL found in share picker: {url}")
                device.press("back")   # close system share picker
                time.sleep(0.4)
                # On some Instagram versions, Copy link auto-dismisses the share sheet;
                # on others it stays open. Check for the dimmer overlay and tap above
                # the sheet to close it cleanly — safer than a blind second back press
                # which would navigate away from the post.
                try:
                    if device.xpath(POST_SHARE_SHEET_SELECTORS.share_sheet_dimmer).exists:
                        device.tap(288, 200)   # tap above the share modal (dimmer zone)
                        time.sleep(0.4)
                except Exception:
                    pass
                return url

        # Step 4: fallback — try clipboard (devices that copy directly)
        try:
            clipboard = device.clipboard
            if clipboard and any(k in clipboard for k in (
                'instagram.com/p/', 'instagram.com/reel/', 'instagram.com/tv/'
            )):
                url = clipboard.strip()
                if logger:
                    logger.debug(f"get_post_url_from_share: URL from clipboard: {url}")
                device.press("back")   # close any remaining sheet
                time.sleep(0.5)
                return url
        except Exception:
            pass

        # Nothing worked — close sheets and return None
        device.press("back")
        time.sleep(0.3)
        if logger:
            logger.warning("get_post_url_from_share: could not retrieve post URL")
        return None

    except Exception as e:
        if logger:
            logger.error(f"get_post_url_from_share: unexpected error: {e}")
        try:
            device.press("back")
        except Exception:
            pass
        return None
