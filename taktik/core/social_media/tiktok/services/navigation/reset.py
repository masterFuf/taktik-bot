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
    """Reset to the TikTok Home tab: reach the shell first, then go home, then check.

    It used to press back a FIXED number of times and then click. Both halves were wrong, and
    together they closed the app. Measured on 2026-08-30, from the feed: the SECOND back already
    lands on the launcher, so three blind presses left TikTok, the home tab was then looked for on
    the launcher, and this returned False with the app shut. Every caller carried on regardless —
    `target_profiles` then ran `navigate_to_user_profile` on the home screen and reported
    `skip_not_found` for all three targets, having never seen TikTok. The Followers and Search
    workflows call this too, between targets: one reset was enough to sink the rest of a run.

    So: back out only while the bottom bar is MISSING (`return_to_tiktok_shell`, which is a no-op
    from the feed), and confirm arrival on `home_tab_selected` rather than on the tap. A tab that
    swallows a tap while a video is mid-transition is the same failure that made
    `change_language` retry its profile tab.
    """
    try:
        if logger:
            logger.info("Returning to TikTok home...")

        if not return_to_tiktok_shell(
            device, logger=logger, max_back_presses=max(1, back_presses),
            back_delay_seconds=back_delay_seconds,
        ):
            if logger:
                logger.warning("Could not get back to the TikTok shell — not clicking blindly")
            return False

        if _selected_home(device):
            return True

        for selector in NAVIGATION_SELECTORS.home_tab:
            try:
                if device.xpath(selector).click_exists(timeout=selector_timeout_seconds):
                    time.sleep(settle_seconds)
                    if _selected_home(device):
                        if logger:
                            logger.info("Back to TikTok home")
                        return True
            except Exception as exc:
                if logger:
                    logger.debug(f"TikTok home selector failed ({selector}): {exc}")

        if logger:
            logger.warning("Could not confirm arrival on the TikTok Home tab")
        return False
    except Exception as exc:
        if logger:
            logger.warning(f"Could not navigate to TikTok home: {exc}")
        return False


def _selected_home(device: Any) -> bool:
    """Is the Home tab the SELECTED one? The outcome, not the tap."""
    try:
        return any(device.xpath(s).exists for s in NAVIGATION_SELECTORS.home_tab_selected)
    except Exception:
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
