"""
Taktik Keyboard helpers shared across Bot platforms.

This module owns IME-specific behavior for the ADB keyboard, while raw ADB
shell execution lives under `taktik.core.shared.device.adb`.
"""

import atexit
import base64
import threading
import time
from typing import Dict, Optional

from loguru import logger

from taktik.core.shared.device.adb import run_adb_shell
from taktik.core.shared.telemetry import emit_step


TAKTIK_KEYBOARD_PKG = "com.alexal1.adbkeyboard"
TAKTIK_KEYBOARD_IME = "com.alexal1.adbkeyboard/.AdbIME"
IME_MESSAGE_B64 = "ADB_INPUT_B64"
IME_CLEAR_TEXT = "ADB_CLEAR_TEXT"
# The keyboard given back when the phone's own was already the ADB one (Gboard, on the Pixels).
GBOARD_IME = "com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME"
_ACTIVE_CACHE_TTL_SECONDS = 120.0
_active_ime_cache: dict[str, float] = {}

# The keyboard each phone had before this process first switched it to the ADB one (None: it could
# not be read). The bot switched and never gave it back: the Pixels ended up with the ADB keyboard
# as their default, useless to a person (decision 6 of Kevin, 2026-09-23).
_original_ime: Dict[str, Optional[str]] = {}
_restore_lock = threading.Lock()
_atexit_registered = False


def _read_default_ime(device_id: str) -> Optional[str]:
    value = (run_adb_shell(device_id, "settings get secure default_input_method") or "").strip()
    return value if value and value != "null" else None


def remember_original_keyboard(device_id: str) -> None:
    """Remember the phone's keyboard before the FIRST switch of this process, and arrange for it
    to be given back when the process ends (the end of the bridge, so of the session)."""
    global _atexit_registered
    with _restore_lock:
        if device_id in _original_ime:
            return
        try:
            _original_ime[device_id] = _read_default_ime(device_id)
        except Exception as exc:  # the switch goes on; the restore falls back on another keyboard
            logger.debug(f"Could not read the keyboard of {device_id}: {exc}")
            _original_ime[device_id] = None
        if not _atexit_registered:
            atexit.register(restore_all_keyboards)
            _atexit_registered = True


def _fallback_keyboard(device_id: str) -> Optional[str]:
    """The first enabled keyboard that is not the ADB one, Gboard first."""
    enabled = [line.strip() for line in (run_adb_shell(device_id, "ime list -s") or "").splitlines()
               if line.strip() and line.strip() != TAKTIK_KEYBOARD_IME]
    if GBOARD_IME in enabled:
        return GBOARD_IME
    return enabled[0] if enabled else None


def restore_original_keyboard(device_id: str) -> bool:
    """Give the phone back the keyboard it had before the session. One safety net: when that
    keyboard was already the ADB one (or unreadable), the first other enabled keyboard, Gboard
    first. Does nothing for a phone this process never switched. Never raises."""
    with _restore_lock:
        if device_id not in _original_ime:
            return False
        original = _original_ime.pop(device_id)
    try:
        target = original if original and original != TAKTIK_KEYBOARD_IME else _fallback_keyboard(device_id)
        if not target:
            logger.warning(f"No keyboard to give back to {device_id}: the ADB keyboard stays")
            return False
        result = run_adb_shell(device_id, f"ime set {target}") or ""
        _active_ime_cache.pop(device_id, None)
        restored = "selected" in result.lower()
        if restored:
            logger.info(f"Keyboard of {device_id} given back: {target}")
        else:
            logger.warning(f"Keyboard of {device_id} not given back ({target}): {result}")
        return restored
    except Exception as exc:
        logger.warning(f"Keyboard of {device_id} not given back: {exc}")
        return False


def restore_all_keyboards() -> int:
    """Give every phone this process switched its keyboard back. Run at the process exit."""
    return sum(1 for device_id in list(_original_ime) if restore_original_keyboard(device_id))


def is_taktik_keyboard_active(device_id: str) -> bool:
    """Check if Taktik Keyboard (ADB Keyboard) is the active IME."""
    cached_at = _active_ime_cache.get(device_id)
    if cached_at and (time.time() - cached_at) < _ACTIVE_CACHE_TTL_SECONDS:
        return True

    try:
        result = run_adb_shell(device_id, "settings get secure default_input_method")
        active = TAKTIK_KEYBOARD_IME in result
        if active:
            _active_ime_cache[device_id] = time.time()
        return active
    except Exception as exc:
        logger.debug(f"Cannot check keyboard status: {exc}")
        return False


def activate_taktik_keyboard(device_id: str) -> bool:
    """Activate Taktik Keyboard as the default IME (the ONE place the bot switches keyboards).

    The phone's own keyboard is remembered first and given back at the end of the session
    (`restore_original_keyboard`).
    """
    try:
        remember_original_keyboard(device_id)
        run_adb_shell(device_id, f"ime enable {TAKTIK_KEYBOARD_IME}")
        result = run_adb_shell(device_id, f"ime set {TAKTIK_KEYBOARD_IME}")

        if "selected" in result.lower():
            logger.debug("Taktik Keyboard activated")
            return True

        logger.warning(f"Failed to activate Taktik Keyboard: {result}")
        return False
    except Exception as exc:
        logger.error(f"Error activating Taktik Keyboard: {exc}")
        return False


def type_with_taktik_keyboard(
    device_id: str,
    text: str,
    delay_mean: int = 80,
    delay_deviation: int = 30,
) -> bool:
    """
    Type text using Taktik Keyboard via ADB broadcast.

    Args:
        device_id: ADB device serial/ID.
        text: Text to type.
        delay_mean: Mean delay between characters in ms.
        delay_deviation: Delay deviation in ms.

    Returns:
        True if successful, False otherwise.
    """
    if not text:
        return True

    try:
        if not is_taktik_keyboard_active(device_id):
            logger.debug("Taktik Keyboard not active, activating")
            if not activate_taktik_keyboard(device_id):
                logger.warning("Could not activate Taktik Keyboard")
                return False

        text_b64 = base64.b64encode(text.encode("utf-8")).decode("utf-8")
        broadcast_cmd = (
            f"am broadcast -a {IME_MESSAGE_B64} --es msg {text_b64} "
            f"--ei delay_mean {delay_mean} --ei delay_deviation {delay_deviation}"
        )
        started_at = time.time()
        result = run_adb_shell(device_id, broadcast_cmd)
        ack_duration = time.time() - started_at

        if result and "error" not in result.lower():
            typing_time = (delay_mean * len(text) + delay_deviation) / 1000
            settle_buffer = 0.15 if len(text) <= 24 else 0.3
            logger.debug(
                f"Taktik Keyboard typing {len(text)} chars "
                f"({typing_time:.1f}s, ack {ack_duration:.1f}s)"
            )
            # Telemetry: never the text itself (passwords/2FA) — only length + cadence.
            emit_step(
                "keystroke", action="type",
                length=len(text), delay_mean=delay_mean, delay_deviation=delay_deviation,
                typing_s=round(typing_time, 3), ack_s=round(ack_duration, 3),
            )
            _active_ime_cache[device_id] = time.time()
            time.sleep(typing_time + settle_buffer)
            return True

        logger.warning(f"Taktik Keyboard broadcast failed: {result}")
        return False
    except Exception as exc:
        logger.error(f"Error using Taktik Keyboard: {exc}")
        return False


def clear_text_with_taktik_keyboard(device_id: str) -> bool:
    """Clear the current text field using Taktik Keyboard."""
    try:
        result = run_adb_shell(device_id, f"am broadcast -a {IME_CLEAR_TEXT}")
        return bool(result) and "error" not in result.lower()
    except Exception as exc:
        logger.error(f"Error clearing text: {exc}")
        return False


def _press_backspace(device_id: str, count: int = 1) -> bool:
    """Delete `count` characters (KEYCODE_DEL = 67) — used to correct a typo."""
    ok = True
    for _ in range(max(0, count)):
        try:
            run_adb_shell(device_id, "input keyevent 67")
            time.sleep(0.04)
        except Exception as exc:
            logger.debug(f"Backspace keyevent failed: {exc}")
            ok = False
    emit_step("keystroke", action="backspace", count=max(0, count), success=ok)
    return ok


def type_text_human(
    device_id: str,
    text: str,
    *,
    typos: bool = True,
    rng=None,
    delay_mean: int = 80,
    delay_deviation: int = 30,
) -> bool:
    """Type `text` like a human: occasional adjacent-key typos that get corrected, and
    think-pauses, on top of the per-character cadence the keyboard already applies.

    Set `typos=False` for fields where a mistake must never be committed even briefly
    (passwords, 2FA codes, login usernames) — that types the exact string, cadence only.
    """
    if not text:
        return True
    if not typos:
        return type_with_taktik_keyboard(device_id, text, delay_mean, delay_deviation)

    from taktik.core.shared.behavior.typing import build_typing_plan

    ok = True
    for op in build_typing_plan(text, rng=rng):
        kind = op[0]
        if kind == "type":
            if not type_with_taktik_keyboard(device_id, op[1], delay_mean, delay_deviation):
                ok = False
        elif kind == "backspace":
            if not _press_backspace(device_id, op[1]):
                ok = False
        elif kind == "pause":
            time.sleep(op[1])
    return ok


__all__ = [
    "run_adb_shell",
    "TAKTIK_KEYBOARD_PKG",
    "TAKTIK_KEYBOARD_IME",
    "IME_MESSAGE_B64",
    "IME_CLEAR_TEXT",
    "is_taktik_keyboard_active",
    "activate_taktik_keyboard",
    "remember_original_keyboard",
    "restore_original_keyboard",
    "restore_all_keyboards",
    "GBOARD_IME",
    "type_with_taktik_keyboard",
    "type_text_human",
    "clear_text_with_taktik_keyboard",
]
