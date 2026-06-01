"""
AppService: launch, stop, and restart mobile apps on connected devices.

Centralizes app lifecycle management for bridge runtimes while package catalogs,
ADB control helpers and inspection helpers live under dedicated owners.
"""

import time
from typing import Optional

from loguru import logger

from bridges.common.device.app_control import force_stop_app
from bridges.common.device.app_inspection import (
    get_installed_app_version,
    is_app_running,
)
from bridges.common.device.app_resolution import resolve_app_config


class AppService:
    """
    Manage one mobile app lifecycle on a connected device.

    Requires a ConnectionService that is already connected.
    """

    def __init__(self, connection, platform: str = "instagram", package_override: Optional[str] = None):
        """
        Args:
            connection: A connected ConnectionService instance.
            platform: Platform key such as "instagram" or "tiktok".
            package_override: Optional package override for cloned apps.
        """
        self._conn = connection
        self._platform = platform
        self._config = resolve_app_config(connection, platform, package_override)

    @property
    def package(self) -> str:
        """Return the effective app package name."""
        return self._config["package"]

    @property
    def activity(self) -> str:
        """Return the effective app main activity."""
        return self._config["activity"]

    def is_installed(self) -> bool:
        """Check whether the effective package is installed on the device."""
        device_manager = self._conn.device_manager
        if device_manager is None:
            logger.error("Cannot check installed: not connected")
            return False
        return device_manager.is_app_installed(self.package)

    def launch(self) -> bool:
        """Launch the app and wait for the configured startup delay."""
        device_manager = self._conn.device_manager
        if device_manager is None:
            logger.error("Cannot launch: not connected")
            return False

        logger.info(f"Launching {self._platform}...")
        result = device_manager.launch_app(self.package, self.activity)
        if result:
            time.sleep(self._config["launch_wait"])
            logger.info(f"{self._platform.capitalize()} launched")
        else:
            logger.error(f"Failed to launch {self._platform}")
        return result

    def stop(self) -> bool:
        """Force-stop the app and wait for the configured stop delay."""
        device_manager = self._conn.device_manager
        if device_manager is None:
            logger.error("Cannot stop: not connected")
            return False

        logger.info(f"Stopping {self._platform}...")
        result = device_manager.stop_app(self.package)
        time.sleep(self._config["stop_wait"])
        return result

    def restart(self) -> bool:
        """Force-stop then relaunch the app for a clean state."""
        logger.info(f"Restarting {self._platform} (force-stop + launch)...")
        self.stop()
        return self.launch()

    def is_running(self) -> bool:
        """Check if the app is currently in the foreground."""
        return is_app_running(self._conn.device, self.package, self._platform)

    def get_installed_version(self) -> Optional[str]:
        """Return the installed app version reported by ADB."""
        return get_installed_app_version(self._conn.device_id, self.package, self._platform)
