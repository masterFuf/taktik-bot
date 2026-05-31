"""Shared core modules for Taktik.

Contains base classes and shared Android/action primitives used by platform
implementations.
"""

from .actions import ActionUtils, SharedBaseAction, parse_count
from .device import BaseDeviceFacade, DeviceManager, Direction
from .input import (
    IME_CLEAR_TEXT,
    IME_MESSAGE_B64,
    TAKTIK_KEYBOARD_IME,
    TAKTIK_KEYBOARD_PKG,
    activate_taktik_keyboard,
    clear_text_with_taktik_keyboard,
    is_taktik_keyboard_active,
    run_adb_shell,
    type_with_taktik_keyboard,
)
from .platform import SocialMediaBase

__all__ = [
    "SharedBaseAction",
    "ActionUtils",
    "parse_count",
    "BaseDeviceFacade",
    "Direction",
    "DeviceManager",
    "run_adb_shell",
    "TAKTIK_KEYBOARD_PKG",
    "TAKTIK_KEYBOARD_IME",
    "IME_MESSAGE_B64",
    "IME_CLEAR_TEXT",
    "is_taktik_keyboard_active",
    "activate_taktik_keyboard",
    "type_with_taktik_keyboard",
    "clear_text_with_taktik_keyboard",
    "SocialMediaBase",
]
