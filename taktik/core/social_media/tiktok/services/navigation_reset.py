"""Reusable TikTok navigation reset helpers."""

from __future__ import annotations

import time
from typing import Any

from taktik.core.social_media.tiktok.ui.selectors import NAVIGATION_SELECTORS


def return_to_tiktok_home(
    device: Any,
    *,
    logger: Any = None,
    back_presses: int = 3,
    back_delay_seconds: float = 0.5,
    selector_timeout_seconds: float = 2.0,
    settle_seconds: float = 1.5,
) -> bool:
    """Best-effort reset to the TikTok Home tab using centralized selectors."""
    try:
        if logger:
            logger.info("Returning to TikTok home...")

        for _ in range(max(0, back_presses)):
            device.press("back")
            time.sleep(back_delay_seconds)

        for selector in NAVIGATION_SELECTORS.home_tab:
            try:
                if device.xpath(selector).click_exists(timeout=selector_timeout_seconds):
                    time.sleep(settle_seconds)
                    if logger:
                        logger.info("Back to TikTok home")
                    return True
            except Exception as exc:
                if logger:
                    logger.debug(f"TikTok home selector failed ({selector}): {exc}")

        if logger:
            logger.warning("Could not confirm TikTok Home tab click")
        return False
    except Exception as exc:
        if logger:
            logger.warning(f"Could not navigate to TikTok home: {exc}")
        return False
