"""Last-resort coordinate fallback of the TikTok publish workflow: the caption field's focus.

The taps of the way to the post screen (Create, the gallery entry, the newest medium) have no
coordinate fallback any more: a tap aims at a node its selectors find, or the workflow stops.
"""

from __future__ import annotations

from typing import Callable


LogFn = Callable[[str, str], None]

DEFAULT_WIDTH = 720
DEFAULT_HEIGHT = 1520
CAPTION_DEFAULT_WIDTH = 576
CAPTION_DEFAULT_HEIGHT = 1280


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
