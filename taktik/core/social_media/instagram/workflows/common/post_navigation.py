"""Shared post navigation functions for scraping/discovery workflows.

All functions take `device` and `logger` as parameters — no class dependency.
"""

import time
from typing import Optional

from ...ui.selectors.shell.screen_state import DETECTION_SELECTORS
from ...ui.selectors.surfaces.post.grid import POST_GRID_SELECTORS
from ...ui.selectors.surfaces.post.likers import POST_LIKERS_SELECTORS
from ...ui.selectors.surfaces.post.share_sheet import POST_SHARE_SHEET_SELECTORS
from ...ui.selectors.surfaces.profile import PROFILE_SELECTORS
from taktik.core.shared.behavior.gesture_primitives import human_scroll_raw
from taktik.core.shared.behavior.grid_entry import GRID_COLUMNS
from .detection import is_in_post_view, is_likers_popup_open


def ensure_profile_grid_tab(device, logger=None) -> bool:
    """Make the POSTS grid the active sub-tab of the profile on screen. True if it is (or now is).

    Instagram remembers the last sub-tab a profile was left on, so landing on a profile does not
    mean the grid is showing. Caught on a device: "Reposted" was active, so no thumbnail selector
    could match and the caller concluded "no posts in grid" on a profile that has posts — then
    scrolled twice looking for them, which on a short profile only pushed the page around. Checking
    the tab costs one dump and removes a whole class of phantom empty grids.
    """
    for selector in PROFILE_SELECTORS.profile_grid_tab_selectors:
        try:
            element = device.xpath(selector)
            if not element.exists:
                continue
            node = element.get()
            if str(node.attrib.get("selected", "")).lower() == "true":
                return True
            if logger:
                logger.debug("Profile is on another sub-tab; selecting the posts grid")
            human_tap = getattr(device, "human_tap", None)
            if callable(human_tap) and human_tap(node.bounds):
                pass
            else:
                node.click()
            time.sleep(1.2)          # let the grid attach before anyone reads thumbnails
            return True
        except Exception as exc:
            if logger:
                logger.debug(f"Could not read the profile sub-tab row: {exc}")
    return False


def open_first_post_of_profile(device, logger=None) -> bool:
    """Open the first post in the current profile's grid."""
    try:
        ensure_profile_grid_tab(device, logger)
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


def open_post_at_position(device, index: int, logger=None) -> bool:
    """Open the profile-grid post at absolute 1-based ``index``, scrolling the grid DOWN (humanized)
    to reveal deeper rows when the cell is not on screen yet. Returns True if the post viewer opened.

    Lets a scan page PAST the initially visible posts (grid cells carry their position in
    content-desc, FR/EN). 3-column grid: row = (index-1)//3 + 1, col = (index-1)%3 + 1. The like
    workflow keeps its own humanized variant (`_open_post_at_position`) for engagement; this
    standalone one only needs the device and is used by read-only scans (e.g. persona style)."""
    if index < 1:
        index = 1
    row = (index - 1) // GRID_COLUMNS + 1
    col = (index - 1) % GRID_COLUMNS + 1
    selector = DETECTION_SELECTORS.post_grid_cell_by_position(row, col)
    try:
        target = None
        for _ in range(8):
            element = device.xpath(selector)
            if element.exists:
                target = element
                break
            # Reveal deeper rows with a humanized grid scroll (never a fixed-coordinate swipe).
            human_scroll_raw(device, "down", distance_ratio=0.6)
            time.sleep(0.7)

        if target is None:
            if logger:
                logger.info(f"open_post_at_position: post #{index} (row {row}, col {col}) not found after scroll")
            return False

        target.click()
        time.sleep(3)
        if is_in_post_view(device, logger):
            return True
        if logger:
            logger.warning(f"open_post_at_position: post #{index} did not open")
        return False

    except Exception as exc:
        if logger:
            logger.error(f"open_post_at_position #{index}: {exc}")
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


def _close_share_sheet(device, logger=None) -> bool:
    """Leave no share sheet behind. Verified: False means it is genuinely still on screen.

    A sheet left open hides whatever comes next — the run that surfaced this ended on four empty
    followers-list scans, ten seconds after the sheet stayed up.
    """
    from ...actions.atomic.interaction.bottom_sheet import dismiss_share_sheet, is_share_sheet_open

    if not is_share_sheet_open(device):
        return True
    closed = dismiss_share_sheet(device, logger)
    if not closed and logger:
        logger.warning("get_post_url_from_share: share sheet still open after every dismiss strategy")
    return closed


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
            _close_share_sheet(device, logger)
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
                # Copy link dismisses the share sheet on some Instagram builds and leaves it up on
                # others. This used to tap a fixed (288, 200) "above the modal" — a point that is
                # INSIDE the sheet once it has expanded to full screen — and then return the URL
                # without checking, so the caller carried on with a modal covering the app.
                _close_share_sheet(device, logger)
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
                _close_share_sheet(device, logger)
                return url
        except Exception:
            pass

        # Nothing worked — close the sheet anyway and return None
        _close_share_sheet(device, logger)
        if logger:
            logger.warning("get_post_url_from_share: could not retrieve post URL")
        return None

    except Exception as e:
        if logger:
            logger.error(f"get_post_url_from_share: unexpected error: {e}")
        try:
            _close_share_sheet(device, logger)
        except Exception:
            pass
        return None
