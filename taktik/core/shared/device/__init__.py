"""Shared device primitives for ADB, ATX, media and permissions."""

from .adb import run_adb_shell, run_adb_shell_process
from .facade import BaseDeviceFacade, Direction
from .manager import DeviceManager
from .media_store import (
    get_android_sdk_version,
    guess_mime_type,
    is_video_file,
    push_and_scan,
    push_media,
    scan_wait_for,
    trigger_media_scan,
)
from .permissions import (
    ALLOW_SELECTORS,
    DENY_SELECTORS,
    DIALOG_INDICATORS,
    PermissionHandler,
    deny_permissions,
    grant_permissions,
)

__all__ = [
    "run_adb_shell",
    "run_adb_shell_process",
    "BaseDeviceFacade",
    "Direction",
    "DeviceManager",
    "get_android_sdk_version",
    "is_video_file",
    "guess_mime_type",
    "push_media",
    "trigger_media_scan",
    "scan_wait_for",
    "push_and_scan",
    "PermissionHandler",
    "grant_permissions",
    "deny_permissions",
    "ALLOW_SELECTORS",
    "DENY_SELECTORS",
    "DIALOG_INDICATORS",
]
