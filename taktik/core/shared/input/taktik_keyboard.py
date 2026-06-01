"""
Taktik Keyboard helpers shared across Bot platforms.

This module owns IME-specific behavior for the ADB keyboard, while raw ADB
shell execution lives under `taktik.core.shared.device.adb`.
"""

import base64
import time

from loguru import logger

from taktik.core.shared.device.adb import run_adb_shell


TAKTIK_KEYBOARD_PKG = "com.alexal1.adbkeyboard"
TAKTIK_KEYBOARD_IME = "com.alexal1.adbkeyboard/.AdbIME"
IME_MESSAGE_B64 = "ADB_INPUT_B64"
IME_CLEAR_TEXT = "ADB_CLEAR_TEXT"
_ACTIVE_CACHE_TTL_SECONDS = 120.0
_active_ime_cache: dict[str, float] = {}


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
    """Activate Taktik Keyboard as the default IME."""
    try:
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
                f"Taktik Keyboard typing '{text[:20]}...' "
                f"({typing_time:.1f}s, ack {ack_duration:.1f}s)"
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


__all__ = [
    "run_adb_shell",
    "TAKTIK_KEYBOARD_PKG",
    "TAKTIK_KEYBOARD_IME",
    "IME_MESSAGE_B64",
    "IME_CLEAR_TEXT",
    "is_taktik_keyboard_active",
    "activate_taktik_keyboard",
    "type_with_taktik_keyboard",
    "clear_text_with_taktik_keyboard",
]
