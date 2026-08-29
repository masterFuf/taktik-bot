"""Reusable TikTok navigation reset helpers."""

from __future__ import annotations

import time
from typing import Any

from taktik.core.social_media.tiktok.ui.selectors.shell.navigation import NAVIGATION_SELECTORS


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


def return_to_tiktok_shell(
    device: Any,
    *,
    logger: Any = None,
    max_back_presses: int = 5,
    back_delay_seconds: float = 1.2,
) -> bool:
    """Back out until the bottom navigation bar is reachable again.

    A follow list, a search page or a visited profile is a full-screen page with NO bottom bar,
    so asking to go to a tab from inside one taps nothing — and the caller reads that as "the
    tab is gone" rather than "we are not where tabs exist". Measured twice on 2026-08-29: the
    follow-graph sync could not reopen a list it had just walked, and the Lab could not open the
    second list after reading the first.

    Unlike `return_to_tiktok_home`, this presses back only while the bar is MISSING, so calling
    it from the feed does nothing at all — which is what makes it safe to call before every
    navigation.
    """
    for _ in range(max(0, max_back_presses)):
        try:
            for selector in NAVIGATION_SELECTORS.profile_tab:
                if device.xpath(selector).exists:
                    return True
        except Exception as exc:
            if logger:
                logger.debug(f"Shell check failed: {exc}")
        device.press("back")
        time.sleep(back_delay_seconds)

    try:
        return any(device.xpath(s).exists for s in NAVIGATION_SELECTORS.profile_tab)
    except Exception:
        return False


__all__ = ["return_to_tiktok_home", "return_to_tiktok_shell"]
