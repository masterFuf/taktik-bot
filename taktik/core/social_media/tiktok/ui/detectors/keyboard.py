"""TikTok keyboard overlay detection."""

from __future__ import annotations

import subprocess
import time
from typing import Callable

from taktik.core.social_media.tiktok.ui.selectors.flows.publish import PUBLISH_COMPOSER_SELECTORS
from taktik.core.social_media.tiktok.ui.xpath import find_element


LogFn = Callable[[str, str], None]


def is_keyboard_visible(device, timeout: float = 1.0) -> bool:
    """Detect visible system/Taktik keyboard overlays from selectors."""
    return find_element(device, PUBLISH_COMPOSER_SELECTORS.keyboard_overlay_indicators, timeout=timeout) is not None


def dismiss_keyboard(
    device,
    device_id: str | None = None,
    timeout: float = 1.0,
    settle_delay: float = 0.35,
    log: LogFn | None = None,
) -> bool:
    """Hide the keyboard without tapping the app preview/editor area."""
    try:
        if not is_keyboard_visible(device, timeout=timeout):
            return True

        if log:
            log("debug", "[keyboard] visible; closing it with Back")

        try:
            device.press("back")
        except Exception:
            if not device_id:
                return False
            subprocess.run(
                ["adb", "-s", device_id, "shell", "input", "keyevent", "4"],
                capture_output=True,
                text=True,
                timeout=5,
            )

        time.sleep(settle_delay)

        hidden = not is_keyboard_visible(device, timeout=timeout)
        if not hidden and log:
            log("debug", "[keyboard] still visible after Back")
        return hidden
    except Exception as exc:
        if log:
            log("debug", f"[keyboard] dismiss failed: {exc}")
        return False
