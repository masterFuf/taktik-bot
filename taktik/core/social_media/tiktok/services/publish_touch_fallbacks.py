"""Last-resort coordinate fallbacks for the TikTok publish workflow."""

from __future__ import annotations

import time
from typing import Callable


LogFn = Callable[[str, str], None]
SleepFn = Callable[[float], None]
ScreenCheckFn = Callable[[], bool]

DEFAULT_WIDTH = 720
DEFAULT_HEIGHT = 1520
CAPTION_DEFAULT_WIDTH = 576
CAPTION_DEFAULT_HEIGHT = 1280


def tap_create_button_fallback(device, *, log: LogFn | None = None) -> bool:
    """Tap the bottom navigation Create slot when selectors do not match."""
    return tap_relative(
        device,
        0.40,
        0.94,
        label="[create] fallback coord tap",
        log=log,
    )


def tap_upload_right_strip_fallback(device, *, log: LogFn | None = None) -> bool:
    """Tap the right-side gallery thumbnail used by several TikTok camera layouts."""
    return tap_relative(
        device,
        0.815,
        0.785,
        label="[upload] fallback A (right-strip)",
        error_label="[upload] fallback A failed",
        log=log,
    )


def tap_upload_bottom_left_fallback(device, *, log: LogFn | None = None) -> bool:
    """Tap the bottom-left gallery thumbnail used by larger TikTok layouts."""
    return tap_relative(
        device,
        0.086,
        0.921,
        label="[upload] fallback B (bottom-left)",
        error_label="[upload] fallback B failed",
        error_level="error",
        log=log,
    )


def tap_first_gallery_item_fallback(
    device,
    *,
    is_camera_creation_screen: ScreenCheckFn | None = None,
    sleep: SleepFn = time.sleep,
    log: LogFn | None = None,
) -> bool:
    """Tap the first gallery item when TikTok exposes no usable selector."""
    try:
        width, height = _display_size(device)
        tap_x = width // 6
        tap_y = int(height * 0.20)
        _log(
            log,
            "warning",
            f"[gallery] XPath selectors failed - coord fallback ({tap_x},{tap_y}). "
            "Provide a dump from this device to add the correct resource-id.",
        )
        device.click(tap_x, tap_y)
        sleep(1.0)

        if is_camera_creation_screen and is_camera_creation_screen():
            _log(log, "warning", "[gallery] coord fallback did not leave the camera screen")
            return False
        return True
    except Exception as exc:
        _log(log, "error", f"[gallery] coord fallback failed: {exc}")
        return False


def tap_caption_focus_fallback(device, *, log: LogFn | None = None) -> bool:
    """Focus the caption area by coordinates when the EditText selector is absent."""
    return tap_relative(
        device,
        0.50,
        0.30,
        default_width=CAPTION_DEFAULT_WIDTH,
        default_height=CAPTION_DEFAULT_HEIGHT,
        label="[caption] focus fallback",
        error_label="[caption] focus fallback failed",
        error_level="warning",
        log=log,
    )


def tap_relative(
    device,
    x_ratio: float,
    y_ratio: float,
    *,
    default_width: int = DEFAULT_WIDTH,
    default_height: int = DEFAULT_HEIGHT,
    label: str,
    error_label: str | None = None,
    error_level: str = "debug",
    log: LogFn | None = None,
) -> bool:
    """Tap a ratio-based coordinate using device display size with safe defaults."""
    try:
        width, height = _display_size(device, default_width=default_width, default_height=default_height)
        tap_x = int(width * x_ratio)
        tap_y = int(height * y_ratio)
        _log(log, "debug", f"{label}: ({tap_x}, {tap_y})")
        device.click(tap_x, tap_y)
        return True
    except Exception as exc:
        _log(log, error_level, f"{error_label or label}: {exc}")
        return False


def _display_size(
    device,
    *,
    default_width: int = DEFAULT_WIDTH,
    default_height: int = DEFAULT_HEIGHT,
) -> tuple[int, int]:
    info = getattr(device, "info", {}) or {}
    return (
        int(info.get("displayWidth", default_width)),
        int(info.get("displayHeight", default_height)),
    )


def _log(log: LogFn | None, level: str, message: str) -> None:
    if log:
        log(level, message)
