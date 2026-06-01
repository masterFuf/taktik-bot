"""
AppService — launch, stop, and restart mobile apps on connected devices.

Centralizes app management for Instagram and TikTok so that package names,
activity names, and timing constants live in ONE place.

Usage:
    from bridges.common.device.connection import ConnectionService
    from bridges.common.device.app_manager import AppService

    conn = ConnectionService("DEVICE_SERIAL")
    conn.connect()

    app = AppService(conn, platform="instagram")
    app.restart()   # force-stop + launch + wait
    app.stop()      # force-stop only
    app.launch()    # launch only
"""

import time
import subprocess
from typing import Optional
from loguru import logger

from bridges.common.device.app_control import force_stop_app
from bridges.common.device.apps import (
    alternatives_for_platform,
    get_app_config,
    known_platforms,
)


class AppService:
    """
    Manages a single mobile app (Instagram or TikTok) on a connected device.

    Requires a ConnectionService that is already connected.
    """

    def __init__(self, connection, platform: str = "instagram", package_override: Optional[str] = None):
        """
        Args:
            connection: A connected ConnectionService instance.
            platform: "instagram" or "tiktok".
            package_override: If set, use this package name instead of the
                              default (for cloned apps like NomixCloner).
        """
        app_config = get_app_config(platform)
        if not app_config:
            raise ValueError(f"Unknown platform '{platform}'. Must be one of: {known_platforms()}")

        self._conn = connection
        self._platform = platform
        self._config = app_config

        if package_override and package_override != self._config["package"]:
            logger.info(f"[AppService] Using clone package: {package_override}")
            self._config["package"] = package_override
            # Taktik-cloner packages (com.taktik.ig*, com.taktik.tk*) don't share
            # the same internal activity class, so skip explicit activity launch.
            # NomixCloner preserves the original activity class, so it's fine.
            if package_override.startswith("com.taktik."):
                self._config["activity"] = None
        elif not package_override:
            # Auto-detect: if the default package is not installed, try alternatives
            # (e.g. com.ss.android.ugc.trill when com.zhiliaoapp.musically is absent)
            dm = connection.device_manager
            alternatives = alternatives_for_platform(platform)
            if dm is not None and alternatives:
                for alt_pkg in alternatives:
                    if dm.is_app_installed(alt_pkg):
                        if alt_pkg != self._config["package"]:
                            logger.info(
                                f"[AppService] Default package '{self._config['package']}' "
                                f"not installed — using '{alt_pkg}' for {platform}"
                            )
                            self._config["package"] = alt_pkg
                        break
                else:
                    logger.warning(
                        f"[AppService] No known {platform} package found on device. "
                        f"Tried: {alternatives}"
                    )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def package(self) -> str:
        """The app package name (e.g. com.instagram.android)."""
        return self._config["package"]

    @property
    def activity(self) -> str:
        """The app main activity."""
        return self._config["activity"]

    def is_installed(self) -> bool:
        """Check if the app is installed on the device."""
        dm = self._conn.device_manager
        if dm is None:
            logger.error("Cannot check installed: not connected")
            return False
        return dm.is_app_installed(self.package)

    def launch(self) -> bool:
        """
        Launch the app.
        Returns True if launch_app() succeeds.
        """
        dm = self._conn.device_manager
        if dm is None:
            logger.error("Cannot launch: not connected")
            return False

        logger.info(f"Launching {self._platform}...")
        result = dm.launch_app(self.package, self.activity)
        if result:
            time.sleep(self._config["launch_wait"])
            logger.info(f"{self._platform.capitalize()} launched")
        else:
            logger.error(f"Failed to launch {self._platform}")
        return result

    def stop(self) -> bool:
        """
        Force-stop the app.
        Returns True if stop_app() succeeds.
        """
        dm = self._conn.device_manager
        if dm is None:
            logger.error("Cannot stop: not connected")
            return False

        logger.info(f"Stopping {self._platform}...")
        result = dm.stop_app(self.package)
        time.sleep(self._config["stop_wait"])
        return result

    def restart(self) -> bool:
        """
        Force-stop then relaunch the app for a clean state.
        Returns True if the app is running after restart.
        """
        logger.info(f"Restarting {self._platform} (force-stop + launch)...")
        self.stop()
        return self.launch()

    def is_running(self) -> bool:
        """Check if the app is currently in the foreground."""
        device = self._conn.device
        if device is None:
            return False
        try:
            current_app = device.app_current()
            return current_app.get('package') == self.package
        except Exception as e:
            logger.warning(f"Could not check if {self._platform} is running: {e}")
            return False

    def get_installed_version(self) -> Optional[str]:
        """
        Detect the installed app version via ADB.

        Returns the versionName string (e.g. "417.0.0.54.77") or None on failure.
        """
        try:
            result = subprocess.run(
                ["adb", "-s", self._conn.device_id,
                 "shell", "dumpsys", "package", self.package],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("versionName="):
                    version = line.split("=", 1)[1].strip()
                    logger.info(f"[AppService] {self._platform} installed version: {version}")
                    return version
            logger.warning(f"[AppService] versionName not found in dumpsys output for {self.package}")
            return None
        except Exception as e:
            logger.warning(f"[AppService] Failed to detect app version: {e}")
            return None
