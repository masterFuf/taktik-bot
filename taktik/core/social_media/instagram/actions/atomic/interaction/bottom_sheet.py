"""Closing an Instagram bottom sheet, whatever sheet it is.

Instagram opens half a dozen bottom sheets (comments, Direct/share, follow options, mute
settings...). Closing one reliably takes the same cascade every time, and until now only the
comments sheet had it: `_close_comment_popup` grew five verified strategies while the share
sheet made do with a single hardcoded `device.tap(288, 200)` meant to land "above the modal",
which lands *inside* it as soon as the sheet is expanded to full screen.

The gesture itself matters as much as where it starts: a swipe (coarse down/move/up) is read as a
fling and drops the sheet exactly one state, while a drag that keeps the finger down and reports
the whole path carries the sheet with it and closes it in one go. Everything here drags.

Two things make a sheet hard to dismiss, and both show up on the Direct share sheet:

  * **The grab bar is anonymous.** On the comments sheet it is
    `bottom_sheet_drag_handle_prism`; on the share sheet it is a bare 88x6 ImageView with no
    resource-id, no content-desc and `clickable=false`. An id-only lookup finds nothing, so the
    handle strategy is skipped even though the bar is right there. `find_drag_handle` therefore
    falls back to geometry: a thin, wide-ish, horizontally centred view sitting at the top of
    the sheet is a grab bar, whatever it is called.

  * **An expanded sheet has no outside, and barely enough room to drag.** Its container and the
    dimmer behind it share the same full-screen bounds, so there is no dimmer left to tap and no
    room above the sheet. And a sheet moves by exactly the distance the finger travels, settling
    closed only once its top passes roughly halfway between collapsed and off-screen: from an
    expanded sheet that takes almost the full height of the screen, so the drag has to start on
    the grab bar near the top. Starting a third of the way down — which is where the sheet's
    content begins — leaves the sheet short and it snaps back to collapsed.

Every strategy re-checks `is_open()` before claiming success: a dismissal that is not verified
is how a caller ends up reporting a URL it captured behind a modal that never went away.
"""

import time
from typing import Callable, Dict, List, Optional

from loguru import logger as _default_logger

from taktik.core.shared.behavior.gesture_primitives import human_drag_between_raw
from ....ui.selectors.shell.popups import POPUP_SELECTORS

# Shape of a grab bar: much wider than it is tall, never fills the width, horizontally centred.
#
# Every threshold is a FRACTION OF THE SCREEN, never a pixel count. The bar measured 6x88 px on a
# 1080x2340 phone; the same bar is roughly 8x117 px on a 1440x3200 one, so a `height <= 24px` test
# would be tight on one device and loose on another. Ratios describe the shape itself, which is
# what actually stays constant across resolutions.
_HANDLE_MAX_HEIGHT_RATIO = 0.012      # 28px on 2340, 38px on 3200 — the bar is ~6px / ~8px
_HANDLE_MIN_WIDTH_RATIO = 0.03        # 32px on 1080, 43px on 1440 — the bar is ~88px / ~117px
_HANDLE_MAX_WIDTH_RATIO = 0.45
_HANDLE_CENTER_TOLERANCE_RATIO = 0.08
# Margin below the app window's top edge before a drag may start: touching down INSIDE the status
# bar pulls the notification shade instead of the sheet. Expressed as a fraction, like the rest.
_SHADE_SAFETY_MARGIN_RATIO = 0.005
# Highest a "tap outside the sheet" may land: below the status bar and the shade pull-down zone.
_OUTSIDE_TAP_MIN_RATIO = 0.12
# A sheet steps EXPANDED -> COLLAPSED -> HIDDEN; two drags suffice, the third is a safety net.
_MAX_DRAG_STEPS = 3


def _screen_size(device) -> tuple:
    """(width, height) in pixels. Falls back to a common phone size if the device cannot say —
    every threshold here is a fraction of these, so a wrong guess skews the shape filter rather
    than pointing a gesture at a fixed coordinate."""
    try:
        info = device.info
        return int(info.get('displayWidth', 1080)), int(info.get('displayHeight', 2340))
    except Exception:
        return 1080, 2340


def _bounds_of(element) -> Optional[Dict[str, int]]:
    try:
        bounds = element.info.get('bounds', {})
        if all(k in bounds for k in ('left', 'top', 'right', 'bottom')):
            return bounds
    except Exception:
        pass
    return None


def _sheet_top(device) -> int:
    """Top edge of the sheet host, or 0 when no sheet is recognised.

    Only the host is needed now: the grab bar is looked up INSIDE the sheet's subtree, so there is
    no need to guess which inner container tracks the expanded/collapsed state. An earlier version
    took the deepest container it could match and landed on the external-share row at the very
    bottom of the sheet, 1800px below the bar it was meant to bracket.
    """
    tops = []
    for selector in POPUP_SELECTORS.bottom_sheet_container_selectors:
        try:
            element = device.xpath(selector)
            if element.exists:
                bounds = _bounds_of(element)
                if bounds:
                    tops.append(int(bounds['top']))
        except Exception:
            continue
    return min(tops) if tops else 0


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

    # No id: look for the shape instead, inside the sheet's own subtree.
    screen_width, screen_height = _screen_size(device)

    screen_center = screen_width / 2
    tolerance = screen_width * _HANDLE_CENTER_TOLERANCE_RATIO
    max_height = screen_height * _HANDLE_MAX_HEIGHT_RATIO
    min_width = screen_width * _HANDLE_MIN_WIDTH_RATIO
    max_width = screen_width * _HANDLE_MAX_WIDTH_RATIO

    candidates = []
    for selector in POPUP_SELECTORS.bottom_sheet_handle_candidates:
        try:
            candidates.extend(device.xpath(selector).all())
        except Exception:
            continue

    best = None
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
        if height <= 0 or height > max_height:
            continue
        if width < min_width or width > max_width:
            continue
        if abs(((left + right) / 2) - screen_center) > tolerance:
            continue
        # The bar is the topmost thing in the sheet; anything thin further down is a divider.
        if best is None or c_top < best['top']:
            best = {
                'x': (left + right) // 2,
                'y': (c_top + bottom) // 2,
                'top': c_top,
                'source': 'geometry',
                'selector': None,
            }

    if best:
        log.debug(f"Sheet grab bar found by geometry at ({best['x']},{best['y']})")
        best.pop('top', None)
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

    screen_width, screen_height = _screen_size(device)

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

    # 3. Drag the sheet down and off the screen.
    #
    # One accompanied drag is enough — checked by hand on a device: press, hold, and carry the
    # sheet all the way down and it closes from full screen in a single gesture. An earlier
    # version used `swipe_coordinates`, whose coarse down/move/up Android reads as a fling; a
    # flung sheet settles one state down (expanded -> collapsed) no matter how far the gesture
    # travelled, which is why it kept stopping at two thirds. The loop below is kept as a safety
    # net for that class of outcome: it drags again while the sheet keeps moving and stops as
    # soon as a pass changes nothing, since repeating a gesture that achieves nothing only
    # delays the caller.
    #
    # Progress is measured on the GRAB BAR, not on the sheet container: the container is a
    # full-screen host that reads the same whether the sheet peeks or fills the screen, while the
    # bar travels with the sheet (y=183 expanded, y=910 collapsed on the device measured).
    end_y = int(screen_height * 0.95)
    center_x = screen_width // 2

    # The post-swipe lookup of one pass is the pre-swipe lookup of the next: locating the bar
    # costs two selector probes plus a subtree scan, and doing it twice per pass was most of the
    # nine seconds this took on the Lab run.
    handle = find_drag_handle(device, log)
    # The app window's top edge does not move while the sheet slides, so read it once.
    shade_floor = _sheet_top(device) + int(screen_height * _SHADE_SAFETY_MARGIN_RATIO)

    for step in range(_MAX_DRAG_STEPS):
        handle_y_before = handle['y'] if handle else None

        # Always reach for the grab bar when it is safe to touch down on it — this is not just
        # "what a person does", it is the only start point with enough room.
        #
        # A bottom sheet moves by exactly the distance the finger travels, and it settles closed
        # only once its top passes roughly halfway between collapsed and off-screen. From an
        # expanded sheet the bar sits near the top of the screen, so a drag from there covers
        # almost the full height and clears that threshold. Starting from the sheet's content
        # instead — a third of the way down — throws away that third: measured on a 1080x2220
        # device, a drag from y=888 moved the sheet's top to 1345 against a ~1842 threshold, so
        # it settled back to collapsed however cleanly the finger tracked. Two passes for one
        # gesture's worth of work.
        #
        # The only reason not to start on the bar is the notification shade, and that risk is a
        # touch-down inside the status bar — which is exactly the strip above the app window, so
        # the window's own top edge is the honest floor rather than a fraction of the screen.
        if handle and handle['y'] >= shade_floor:
            start_x, start_y = handle['x'], handle['y']
            how = f"handle drag ({handle['source']})"
            duration = 0.6
        else:
            if handle:
                log.debug(f"Grab bar at y={handle['y']} is inside the status bar (floor {shade_floor}) "
                          f"— dragging from the content instead")
            start_x = center_x
            start_y = int(screen_height * 0.40)
            how = "content drag"
            duration = 0.7

        log.debug(f"{how} #{step + 1}: ({start_x},{start_y}) -> ({start_x},{end_y})")
        # Accompanied drag, not a swipe. A coarse down/move/up reads as a fling and the sheet
        # settles one state down however far the gesture went — which is why an expanded sheet
        # only ever collapsed to two thirds. Keeping the finger down and reporting the whole
        # path carries the sheet along, and it is already at the bottom when the finger lifts.
        human_drag_between_raw(device, (start_x, start_y), (start_x, end_y), duration, log)
        time.sleep(0.7)

        if not is_open():
            log.debug(f"Sheet closed via {how} (pass {step + 1})")
            return True

        handle = find_drag_handle(device, log)
        handle_y_after = handle['y'] if handle else None
        if handle_y_before is not None and handle_y_after is not None:
            if handle_y_after <= handle_y_before:
                log.debug(f"Sheet did not move (grab bar {handle_y_before} -> {handle_y_after}) — stopping")
                break
            log.debug(f"Sheet collapsed a step (grab bar {handle_y_before} -> {handle_y_after}), dragging again")

    log.warning("Sheet still open after every dismiss strategy")
    return False


def sheet_outside_tap_point(device):
    """A point on the page BEHIND the sheet, or None when the sheet leaves nothing exposed.

    "Tap outside to dismiss" only means something while the sheet peeks: expanded, its container
    and the dimmer share the same full-screen bounds, and a tap meant for the page lands on the
    sheet's own content — on the Direct share sheet, on a recipient avatar.
    """
    screen_width, screen_height = _screen_size(device)

    # The grab bar rides the sheet's top edge and is findable in both states, unlike the
    # container, which is a full-screen host.
    handle = find_drag_handle(device)
    top = handle['y'] if handle else _sheet_top(device)
    if not top:
        return None

    # Leave a margin below the status bar so the tap cannot land on it or pull the shade.
    lowest_safe = int(screen_height * _OUTSIDE_TAP_MIN_RATIO)
    if top <= lowest_safe:
        return None
    return screen_width // 2, (lowest_safe + top) // 2


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
