"""Closing an Instagram bottom sheet, whatever sheet it is.

Instagram opens half a dozen bottom sheets (comments, Direct/share, follow options, mute
settings...). Closing one reliably takes the same cascade every time, and until now only the
comments sheet had it: `_close_comment_popup` grew five verified strategies while the share
sheet made do with a single hardcoded `device.tap(288, 200)` meant to land "above the modal",
which lands *inside* it as soon as the sheet is expanded to full screen.

Two things make a sheet hard to dismiss, and both show up on the Direct share sheet:

  * **The grab bar is anonymous.** On the comments sheet it is
    `bottom_sheet_drag_handle_prism`; on the share sheet it is a bare 88x6 ImageView with no
    resource-id, no content-desc and `clickable=false`. An id-only lookup finds nothing, so the
    handle strategy is skipped even though the bar is right there. `find_drag_handle` therefore
    falls back to geometry: a thin, wide-ish, horizontally centred view sitting at the top of
    the sheet is a grab bar, whatever it is called.

  * **An expanded sheet has no outside.** Its container and the dimmer behind it share the same
    full-screen bounds, so there is no dimmer left to tap and no room above the sheet. Dragging
    the handle is out too — from that high up the gesture pulls the notification shade down
    instead. What works is a drag starting inside the sheet's own content, which is why the
    centre swipe is the strategy that actually closes these.

Every strategy re-checks `is_open()` before claiming success: a dismissal that is not verified
is how a caller ends up reporting a URL it captured behind a modal that never went away.
"""

import time
from typing import Callable, Dict, List, Optional

from loguru import logger as _default_logger

from ....ui.selectors.shell.popups import POPUP_SELECTORS

# A grab bar is much wider than it is tall, never fills the width, and sits centred.
_HANDLE_MAX_HEIGHT_PX = 24
_HANDLE_MIN_WIDTH_PX = 40
_HANDLE_MAX_WIDTH_RATIO = 0.45
_HANDLE_CENTER_TOLERANCE_RATIO = 0.08
# How far below the sheet's top edge the bar may sit before it stops being a grab bar.
_HANDLE_TOP_BAND_PX = 120
# Above this, a handle drag would start in the status-bar pull-down zone.
_FULLSCREEN_HANDLE_RATIO = 0.10


def _bounds_of(element) -> Optional[Dict[str, int]]:
    try:
        bounds = element.info.get('bounds', {})
        if all(k in bounds for k in ('left', 'top', 'right', 'bottom')):
            return bounds
    except Exception:
        pass
    return None


def _sheet_top(device) -> int:
    """Top edge of the open sheet, or 0 when no container is recognised."""
    for selector in POPUP_SELECTORS.bottom_sheet_container_selectors:
        try:
            element = device.xpath(selector)
            if element.exists:
                bounds = _bounds_of(element)
                if bounds:
                    return int(bounds['top'])
        except Exception:
            continue
    return 0


def find_drag_handle(device, log=None) -> Optional[Dict[str, object]]:
    """Locate the sheet's grab bar. Returns {x, y, source} or None.

    `source` is 'id' or 'geometry' — the Lab surfaces it so a silent fallback to geometry is
    visible rather than guessed at.
    """
    log = log or _default_logger

    for selector in POPUP_SELECTORS.bottom_sheet_drag_handle_selectors:
        try:
            element = device.xpath(selector)
            if element.exists:
                bounds = _bounds_of(element)
                if bounds:
                    return {
                        'x': (bounds['left'] + bounds['right']) // 2,
                        'y': (bounds['top'] + bounds['bottom']) // 2,
                        'source': 'id',
                        'selector': selector,
                    }
        except Exception:
            continue

    # No id: look for the shape instead. Bounded to the sheet's own top band so a thin divider
    # further down the page cannot pass for a grab bar.
    try:
        info = device.info
        screen_width = int(info.get('displayWidth', 1080))
    except Exception:
        screen_width = 1080

    top = _sheet_top(device)
    if not top:
        return None

    screen_center = screen_width / 2
    tolerance = screen_width * _HANDLE_CENTER_TOLERANCE_RATIO
    best = None

    try:
        candidates = device.xpath(POPUP_SELECTORS.bottom_sheet_handle_candidates).all()
    except Exception:
        candidates = []

    for candidate in candidates:
        try:
            bounds = candidate.bounds  # (left, top, right, bottom)
        except Exception:
            continue
        if not bounds or len(bounds) != 4:
            continue
        left, c_top, right, bottom = (int(v) for v in bounds)
        height = bottom - c_top
        width = right - left
        if height <= 0 or height > _HANDLE_MAX_HEIGHT_PX:
            continue
        if width < _HANDLE_MIN_WIDTH_PX or width > screen_width * _HANDLE_MAX_WIDTH_RATIO:
            continue
        if c_top < top or c_top > top + _HANDLE_TOP_BAND_PX:
            continue
        if abs(((left + right) / 2) - screen_center) > tolerance:
            continue
        # Several may match (bar + its wrapper): the thinnest one is the bar itself.
        if best is None or height < best['height']:
            best = {
                'x': (left + right) // 2,
                'y': (c_top + bottom) // 2,
                'height': height,
                'source': 'geometry',
                'selector': None,
            }

    if best:
        log.debug(f"Sheet grab bar found by geometry at ({best['x']},{best['y']}) h={best['height']}px")
        best.pop('height', None)
    return best


def dismiss_bottom_sheet(
    device,
    is_open: Callable[[], bool],
    log=None,
    back_attempts: int = 3,
    defocus_selectors: Optional[List[str]] = None,
) -> bool:
    """Close the open bottom sheet, verifying after each attempt. True when it is gone.

    `is_open` is the caller's own predicate — "is MY sheet still up" beats "is any sheet up",
    which would report success the moment one sheet replaced another.
    """
    log = log or _default_logger

    if not is_open():
        return True

    try:
        info = device.info
        screen_height = int(info.get('displayHeight', 1920))
        screen_width = int(info.get('displayWidth', 1080))
    except Exception:
        screen_height, screen_width = 1920, 1080

    # 1. Defocus — a focused text field eats the first back press.
    for selector in (defocus_selectors or []):
        try:
            element = device.xpath(selector)
            if element.exists:
                element.click()
                time.sleep(0.5)
                if not is_open():
                    log.debug("Sheet closed by defocus click")
                    return True
                break
        except Exception:
            continue

    # 2. Back, verified each time.
    for attempt in range(back_attempts):
        try:
            device.press("back")
        except Exception as exc:
            log.debug(f"Sheet dismiss: back press failed ({exc})")
            break
        time.sleep(0.9)
        if not is_open():
            log.debug(f"Sheet closed after {attempt + 1} back press(es)")
            return True

    # 3. Drag the grab bar down — only while the sheet is not expanded to the top.
    handle = find_drag_handle(device, log)
    if handle:
        if handle['y'] < int(screen_height * _FULLSCREEN_HANDLE_RATIO):
            log.debug(f"Sheet expanded (handle y={handle['y']}) — a drag from there opens the shade, skipping")
        else:
            end_y = int(screen_height * 0.95)
            log.debug(f"Dragging sheet handle ({handle['source']}): ({handle['x']},{handle['y']}) -> ({handle['x']},{end_y})")
            try:
                device.swipe_coordinates(handle['x'], handle['y'], handle['x'], end_y, 0.3)
            except AttributeError:
                device.swipe(handle['x'], handle['y'], handle['x'], end_y, duration=0.3)
            time.sleep(0.7)
            if not is_open():
                log.debug("Sheet closed via handle drag")
                return True

    # 4. Drag from inside the sheet's content. The one that works on an expanded sheet.
    center_x = screen_width // 2
    start_y = int(screen_height * 0.40)
    end_y = int(screen_height * 0.92)
    log.debug(f"Centre swipe: ({center_x},{start_y}) -> ({center_x},{end_y})")
    try:
        device.swipe_coordinates(center_x, start_y, center_x, end_y, 0.4)
    except AttributeError:
        device.swipe(center_x, start_y, center_x, end_y, duration=0.4)
    time.sleep(0.7)
    if not is_open():
        log.debug("Sheet closed via centre swipe")
        return True

    log.warning("Sheet still open after every dismiss strategy")
    return False


def is_share_sheet_open(device) -> bool:
    """Whether the Direct / share sheet reached from a post's share button is up."""
    for selector in POPUP_SELECTORS.share_sheet_indicators:
        try:
            if device.xpath(selector).exists:
                return True
        except Exception:
            continue
    return False


def dismiss_share_sheet(device, log=None) -> bool:
    """Close the Direct / share sheet. Verified — returns False if it is still up."""
    return dismiss_bottom_sheet(device, lambda: is_share_sheet_open(device), log=log)
