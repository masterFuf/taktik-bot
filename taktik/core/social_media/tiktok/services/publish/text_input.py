"""Caption text input helpers for TikTok publish.

The caption is typed by Taktik Keyboard or not at all: a text written at once through another
channel (`adb shell input text`) is a signal no person gives. A caption the keyboard cannot type
fails the fill, and the workflow stops before Post.
"""

from __future__ import annotations

from typing import Callable


LogFn = Callable[[str, str], None]
ActivateKeyboardFn = Callable[[str], bool]
ClearKeyboardFn = Callable[[str], bool]
TypeKeyboardFn = Callable[..., bool]


def clear_caption_text(
    device_id: str,
    *,
    activate_keyboard: ActivateKeyboardFn | None = None,
    clear_keyboard: ClearKeyboardFn | None = None,
    log: LogFn | None = None,
) -> bool:
    """Clear focused caption text through Taktik Keyboard. False when the keyboard could not be
    activated: nothing was cleared."""
    try:
        if activate_keyboard is None or clear_keyboard is None:
            from taktik.core.shared.input.taktik_keyboard import (
                activate_taktik_keyboard,
                clear_text_with_taktik_keyboard,
            )

            activate_keyboard = activate_keyboard or activate_taktik_keyboard
            clear_keyboard = clear_keyboard or clear_text_with_taktik_keyboard

        if not activate_keyboard(device_id):
            _log(log, "warning", "[caption] Taktik Keyboard not active: caption not cleared")
            return False
        return bool(clear_keyboard(device_id))
    except Exception as exc:
        _log(log, "debug", f"[caption] Taktik Keyboard clear failed: {exc}")
        return False


def type_caption_text(
    device_id: str,
    text: str,
    *,
    delay_mean: int = 80,
    delay_deviation: int = 30,
    type_keyboard: TypeKeyboardFn | None = None,
    log: LogFn | None = None,
) -> bool:
    """Type caption text through Taktik Keyboard. False when it could not: nothing else types it."""
    if not text:
        return True

    try:
        if type_keyboard is None:
            from taktik.core.shared.input.taktik_keyboard import type_with_taktik_keyboard

            type_keyboard = type_with_taktik_keyboard

        if type_keyboard(
            device_id,
            text,
            delay_mean=delay_mean,
            delay_deviation=delay_deviation,
        ):
            _log(log, "debug", "[caption] text inserted with Taktik Keyboard")
            return True
    except Exception as exc:
        _log(log, "error", f"[caption] Taktik Keyboard failed: {exc}")
        return False

    _log(log, "error", "[caption] Taktik Keyboard could not type the text: nothing pasted")
    return False


def type_caption_checked(
    device,
    device_id: str,
    text: str,
    *,
    delay_mean: int = 80,
    delay_deviation: int = 30,
    log: LogFn | None = None,
) -> bool:
    """Make the focused caption field hold exactly `text`: Taktik Keyboard, read back and retyped
    once (`type_text_checked`). False when the field still does not hold it: nothing is pasted."""
    if not text:
        return True

    from taktik.core.shared.input.taktik_keyboard import type_text_checked

    if type_text_checked(device, device_id, text, typos=False,
                         delay_mean=delay_mean, delay_deviation=delay_deviation):
        _log(log, "debug", "[caption] text inserted with Taktik Keyboard")
        return True
    _log(log, "error", "[caption] the caption field does not hold the caption: nothing pasted")
    return False


def _log(log: LogFn | None, level: str, message: str) -> None:
    if log:
        log(level, message)
