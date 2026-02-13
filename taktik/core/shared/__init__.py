"""
Shared core modules for Taktik.
Contains base classes and utilities shared between Instagram and TikTok.

Structure:
    shared/
    ├── actions/        — SharedBaseAction (foundation for all platform actions)
    ├── device/         — BaseDeviceFacade + DeviceManager (ADB/uiautomator2)
    ├── input/          — Taktik Keyboard (ADB Keyboard utilities)
    ├── platform/       — SocialMediaBase (abstract platform interface)
    └── utils/          — ActionUtils + parse_count (common parsers)
"""

from .actions import SharedBaseAction
from .device import BaseDeviceFacade, Direction, DeviceManager
from .input import (
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
from .platform import SocialMediaBase
from .utils import ActionUtils, parse_count

__all__ = [
    # actions/
    'SharedBaseAction',
    # device/
    'BaseDeviceFacade',
    'Direction',
    'DeviceManager',
    # input/
    'run_adb_shell',
    'TAKTIK_KEYBOARD_PKG',
    'TAKTIK_KEYBOARD_IME',
    'IME_MESSAGE_B64',
    'IME_CLEAR_TEXT',
    'is_taktik_keyboard_active',
    'activate_taktik_keyboard',
    'type_with_taktik_keyboard',
    'clear_text_with_taktik_keyboard',
    # platform/
    'SocialMediaBase',
    # utils/
    'ActionUtils',
    'parse_count',
]
