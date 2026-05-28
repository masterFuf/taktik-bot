"""TikTok keyboard overlay detection."""

from __future__ import annotations

from taktik.core.social_media.tiktok.ui.selectors import PUBLISH_SELECTORS
from taktik.core.social_media.tiktok.ui.xpath import find_element


def is_keyboard_visible(device, timeout: float = 1.0) -> bool:
    """Detect visible system/Taktik keyboard overlays from selectors."""
    return find_element(device, PUBLISH_SELECTORS.keyboard_overlay_indicators, timeout=timeout) is not None
