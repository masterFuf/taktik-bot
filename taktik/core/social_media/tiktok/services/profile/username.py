"""Reusable TikTok profile username extraction helpers."""

from __future__ import annotations

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
