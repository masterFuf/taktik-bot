"""Shared device — facade (UI wrapper), manager (ADB connection/ATX), media_store (gallery push/scan), permissions (Android dialog handler)."""

from .facade import BaseDeviceFacade, Direction
from .manager import DeviceManager
from .media_store import (
    get_android_sdk_version,
    is_video_file,
    guess_mime_type,
    push_media,
    trigger_media_scan,
    scan_wait_for,
    push_and_scan,
)
from .permissions import (
    PermissionHandler,
    grant_permissions,
    deny_permissions,
    ALLOW_SELECTORS,
    DENY_SELECTORS,
    DIALOG_INDICATORS,
)

__all__ = [
    'BaseDeviceFacade',
    'Direction',
    'DeviceManager',
    'get_android_sdk_version',
    'is_video_file',
    'guess_mime_type',
    'push_media',
    'trigger_media_scan',
    'scan_wait_for',
    'push_and_scan',
    # permissions
    'PermissionHandler',
    'grant_permissions',
    'deny_permissions',
    'ALLOW_SELECTORS',
    'DENY_SELECTORS',
    'DIALOG_INDICATORS',
]
