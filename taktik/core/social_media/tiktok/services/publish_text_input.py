"""Caption text input helpers for TikTok publish."""

from __future__ import annotations

import subprocess
from typing import Callable


LogFn = Callable[[str, str], None]
RunFn = Callable[..., subprocess.CompletedProcess]
ActivateKeyboardFn = Callable[[str], object]
ClearKeyboardFn = Callable[[str], bool]
TypeKeyboardFn = Callable[..., bool]


def clear_caption_text(
    device_id: str,
    *,
    activate_keyboard: ActivateKeyboardFn | None = None,
    clear_keyboard: ClearKeyboardFn | None = None,
    log: LogFn | None = None,
) -> bool:
    """Clear focused caption text through Taktik Keyboard."""
    try:
        if activate_keyboard is None or clear_keyboard is None:
            from taktik.core.shared.input.taktik_keyboard import (
                activate_taktik_keyboard,
                clear_text_with_taktik_keyboard,
            )

            activate_keyboard = activate_keyboard or activate_taktik_keyboard
            clear_keyboard = clear_keyboard or clear_text_with_taktik_keyboard

        activate_keyboard(device_id)
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
    run: RunFn = subprocess.run,
    log: LogFn | None = None,
) -> bool:
    """Type caption text through Taktik Keyboard, then ASCII-only ADB fallback."""
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
        _log(log, "debug", f"[caption] Taktik Keyboard failed: {exc}")

    return type_ascii_text_with_adb(device_id, text, run=run, log=log)


def type_ascii_text_with_adb(
    device_id: str,
    text: str,
    *,
    run: RunFn = subprocess.run,
    log: LogFn | None = None,
) -> bool:
    """Insert ASCII text through `adb shell input text`."""
    if not all(ord(ch) < 128 for ch in text):
        return False

    try:
        result = run(
            ["adb", "-s", device_id, "shell", "input", "text", escape_adb_input_text(text)],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if result.returncode == 0:
            _log(log, "debug", "[caption] text inserted with adb input text")
            return True
        _log(log, "debug", f"[caption] adb input text failed: {result.stderr}")
    except Exception as exc:
        _log(log, "debug", f"[caption] adb input text exception: {exc}")

    return False


def escape_adb_input_text(text: str) -> str:
    """Escape text for Android's simple `input text` command."""
    escaped = text.replace("\\", "\\\\").replace(" ", "%s")
    return escaped.replace("&", "\\&").replace("|", "\\|").replace(";", "\\;")


def _log(log: LogFn | None, level: str, message: str) -> None:
    if log:
        log(level, message)
