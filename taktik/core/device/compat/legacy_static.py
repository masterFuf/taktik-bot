"""Legacy static device helpers kept for backward compatibility.

Canonical implementation owner:
    `taktik.core.shared.device.manager.DeviceManager`

This module intentionally preserves the historic static API used by older
bridges, scripts and tests:

    - `DeviceManager.get_connected_devices()`
    - `DeviceManager.connect_to_device()`
    - `DeviceManager.launch_app(device, package_name)`

New runtime logic must live in `taktik.core.shared.device/**`.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import uiautomator2 as u2

from taktik.core.shared.device.manager import DeviceManager as SharedDeviceManager

logger = logging.getLogger(__name__)


class DeviceManager:
    """Compatibility facade around the shared device manager.

    The legacy `taktik.core.device` API predates `shared/device/**` and is
    still consumed by a few debug/test bridges. The shared device manager owns
    the actual connection/ATX behavior; this class only preserves the old
    static call style until callers are migrated.
    """

    @staticmethod
    def list_devices():
        """Return the raw shared-device inventory for legacy callers."""
        return SharedDeviceManager.list_devices()

    @staticmethod
    def get_connected_devices() -> List[str]:
        """Return only ADB devices in the `device` state.

        Keeps the historical return shape (`List[str]`) even though the shared
        manager exposes richer records (`{"id": ..., "status": ...}`).
        """
        try:
            return [
                entry["id"]
                for entry in SharedDeviceManager.list_devices()
                if entry.get("status") == "device"
            ]
        except Exception as exc:
            logger.error("Error retrieving devices: %s", exc)
            return []

    @staticmethod
    def connect_to_device(
        device_id: str,
        *,
        verify_atx: bool = False,
    ) -> Optional[u2.Device]:
        """Return a raw `uiautomator2` device for legacy callers.

        `verify_atx` defaults to `False` to preserve the previous "connect
        quickly, do not auto-repair" behavior of this compatibility path.
        """
        try:
            manager = SharedDeviceManager(device_id=device_id)
            if manager.connect(verify_atx=verify_atx):
                logger.info("Connected to device %s", device_id)
                return manager.device
        except Exception as exc:
            logger.error("Error connecting to device %s: %s", device_id, exc)
        return None

    @staticmethod
    def launch_app(
        device: u2.Device,
        package_name: str,
        activity: Optional[str] = None,
        stop_first: bool = False,
    ) -> bool:
        """Launch an app from a raw connected device.

        Kept as a thin adapter because legacy callers already hold a raw device
        object, not a shared `DeviceManager` instance.
        """
        try:
            if stop_first:
                device.app_stop(package_name)
            if activity:
                device.app_start(package_name, activity)
            else:
                device.app_start(package_name)
            logger.info("Application %s launched successfully", package_name)
            return True
        except Exception as exc:
            logger.error("Error launching application %s: %s", package_name, exc)
            return False

    @staticmethod
    def stop_app(device: u2.Device, package_name: str) -> bool:
        """Stop an app from a raw connected device."""
        try:
            device.app_stop(package_name)
            logger.info("Application %s stopped successfully", package_name)
            return True
        except Exception as exc:
            logger.error("Error stopping application %s: %s", package_name, exc)
            return False

    @staticmethod
    def is_app_installed(device: u2.Device, package_name: str) -> bool:
        """Check installation status from a raw connected device."""
        try:
            return device.app_info(package_name) is not None
        except Exception as exc:
            logger.error("Error checking installation of %s: %s", package_name, exc)
            return False
