"""Reusable helpers for TikTok followers list rows."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS

FOLLOWER_USERNAME_TAP_X = 280
PROFILE_LOAD_SETTLE_SECONDS = 1.5


def find_follower_rows(
    device: Any,
    selectors=FOLLOWERS_SELECTORS,
    *,
    logger: Any = None,
) -> List[Dict[str, Any]]:
    """Find visible follower rows and match each row with its username."""
    rows: List[Dict[str, Any]] = []

    try:
        buttons = _first_xpath_all(device, selectors.follower_any_button)
        username_elements = _first_xpath_all(device, selectors.follower_username)

        if logger:
            logger.debug(f"Found {len(buttons)} follow buttons")

        for button in buttons:
            try:
                bounds = get_element_bounds(button)
                username = find_username_for_bounds(username_elements, bounds)

                rows.append(
                    {
                        "button": button,
                        "status": get_element_text(button),
                        "bounds": bounds,
                        "username": username,
                    }
                )
                if logger:
                    logger.debug(
                        f"Found follower @{username} with status: {get_element_text(button)}"
                    )
            except Exception as exc:
                if logger:
                    logger.debug(f"Error processing follower row: {exc}")
    except Exception as exc:
        if logger:
            logger.debug(f"Error finding follower rows: {exc}")

    return rows


def find_username_for_bounds(username_elements: List[Any], row_bounds: Dict[str, int]) -> Optional[str]:
    """Return the username element whose vertical bounds overlap a row."""
    for element in username_elements:
        element_bounds = get_element_bounds(element)
        if vertical_bounds_overlap(element_bounds, row_bounds):
            return get_element_text(element)
    return None


def vertical_bounds_overlap(first: Dict[str, int], second: Dict[str, int]) -> bool:
    """Return True when two Android bounds overlap vertically."""
    return first.get("top", 0) < second.get("bottom", 0) and first.get("bottom", 0) > second.get("top", 0)


def tap_follower_username(
    device: Any,
    row_info: Dict[str, Any],
    *,
    logger: Any = None,
    username_tap_x: int = FOLLOWER_USERNAME_TAP_X,
    settle_seconds: float = PROFILE_LOAD_SETTLE_SECONDS,
) -> bool:
    """Tap the username area of a follower row, avoiding the avatar story tap."""
    tap_point = follower_username_tap_point(row_info.get("bounds", {}), username_tap_x=username_tap_x)
    if not tap_point:
        return False

    click_x, click_y = tap_point
    username = row_info.get("username", "")
    if logger:
        logger.debug(f"Clicking username area at ({click_x}, {click_y}) for @{username}")

    device.click(click_x, click_y)
    time.sleep(settle_seconds)
    return True


def follower_username_tap_point(
    bounds: Dict[str, int],
    *,
    username_tap_x: int = FOLLOWER_USERNAME_TAP_X,
) -> Optional[Tuple[int, int]]:
    """Calculate the tap point for the username text area of a follower row."""
    if not bounds:
        return None

    top = bounds.get("top", 0)
    bottom = bounds.get("bottom", 0)
    if bottom <= top:
        return None

    return username_tap_x, (top + bottom) // 2


def get_element_bounds(element: Any) -> Dict[str, int]:
    info = getattr(element, "info", {}) or {}
    return info.get("bounds", {}) or {}


def get_element_text(element: Any) -> str:
    return getattr(element, "text", "") or ""


def _first_xpath_all(device: Any, selector_candidates: List[str]) -> List[Any]:
    for selector in selector_candidates:
        elements = device.xpath(selector).all()
        if elements:
            return elements
    return []
