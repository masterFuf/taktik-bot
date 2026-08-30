"""Reusable TikTok profile username extraction helpers."""

from __future__ import annotations

import time
from typing import Any

from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS

UNKNOWN_USERNAME = "unknown"


def clean_profile_username(value: Any) -> str:
    """Return a profile username without the leading at-sign."""
    text = str(value or "").strip()
    if not text:
        return ""
    return text.lstrip("@").strip()


def username_from_content_description(description: Any) -> str:
    """Extract the first username mention from an Android content description."""
    text = str(description or "")
    if "@" not in text:
        return ""
    candidate = text.split("@", 1)[1].strip().split()[0]
    return clean_profile_username(candidate).strip(".,;:")


def get_current_profile_username(device: Any, selectors=PROFILE_SELECTORS) -> str:
    """Extract the username from the current TikTok profile screen."""
    for selector in selectors.username:
        username_elem = device.xpath(selector)
        if username_elem.exists:
            text = _get_element_text(username_elem)
            username = clean_profile_username(text)
            if username:
                return username

    for selector in selectors.username_content_description:
        username_elem = device.xpath(selector)
        if username_elem.exists:
            info = getattr(username_elem, "info", {}) or {}
            username = username_from_content_description(
                info.get("contentDescription")
                or info.get("content-desc")
                or info.get("description")
            )
            if username:
                return username

    return UNKNOWN_USERNAME


def _get_element_text(element: Any) -> str:
    if hasattr(element, "get_text"):
        return element.get_text() or ""
    return getattr(element, "text", "") or ""

def _wait_for_any(device: Any, selectors: Any, timeout: float) -> bool:
    """True as soon as one of the selectors resolves, polling until the timeout runs out.

    Same polling shape as `BaseAction._element_exists`; written here because this module is a
    service and has no action instance to borrow it from.
    """
    deadline = time.time() + timeout
    while True:
        for selector in selectors or ():
            try:
                if device.xpath(selector).exists:
                    return True
            except Exception:
                continue
        if time.time() >= deadline:
            return False
        time.sleep(0.3)


def read_open_profile_handle(device: Any, *, label: str = "", timeout: float = 6.0) -> str:
    """The handle of the profile that just opened, or "" when a profile did not open.

    The second half of every "this row shows a display name, I need the username" road, held in
    one place because TikTok renders a display name on ALL of them: the new-followers page, the
    comment sheet, a mention. Reading the name off the row and searching for it looks for a person
    who does not exist under that name.

    Checks ARRIVAL, not the tap: a row that opened a conversation, an interstitial, or nothing at
    all must not be read as a profile. That is how a verdict ends up describing the wrong screen.
    """
    if not _wait_for_any(device, PROFILE_SELECTORS.profile_page_indicator, timeout):
        return ""

    handle = get_current_profile_username(device)
    if not handle or handle == UNKNOWN_USERNAME:
        return ""
    return clean_profile_username(handle)

