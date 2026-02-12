"""Shared input — Taktik Keyboard (ADB Keyboard) utilities."""

from .taktik_keyboard import (
    run_adb_shell,
    TAKTIK_KEYBOARD_PKG,
    TAKTIK_KEYBOARD_IME,
    IME_MESSAGE_B64,
    IME_CLEAR_TEXT,
    is_taktik_keyboard_active,
    activate_taktik_keyboard,
    type_with_taktik_keyboard,
    clear_text_with_taktik_keyboard,
)

__all__ = [
    'run_adb_shell',
    'TAKTIK_KEYBOARD_PKG',
    'TAKTIK_KEYBOARD_IME',
    'IME_MESSAGE_B64',
    'IME_CLEAR_TEXT',
    'is_taktik_keyboard_active',
    'activate_taktik_keyboard',
    'type_with_taktik_keyboard',
    'clear_text_with_taktik_keyboard',
]
