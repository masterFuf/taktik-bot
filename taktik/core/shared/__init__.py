"""
Shared core modules for Taktik.
Contains base classes and utilities shared between Instagram and TikTok.
"""

from .device_facade import BaseDeviceFacade, Direction
from .base_action import SharedBaseAction
from .utils import ActionUtils, parse_count
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
    'BaseDeviceFacade',
    'Direction',
    'SharedBaseAction',
    'ActionUtils',
    'parse_count',
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
