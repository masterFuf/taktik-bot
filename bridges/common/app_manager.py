"""
AppService — launch, stop, and restart mobile apps on connected devices.

Centralizes app management for Instagram and TikTok so that package names,
activity names, and timing constants live in ONE place.

Usage:
    from bridges.common.connection import ConnectionService
    from bridges.common.app_manager import AppService

    conn = ConnectionService("DEVICE_SERIAL")
    conn.connect()

    app = AppService(conn, platform="instagram")
    app.restart()   # force-stop + launch + wait
    app.stop()      # force-stop only
    app.launch()    # launch only
"""

import time
from typing import Optional
from loguru import logger


# ── App constants ────────────────────────────────────────────────────
APPS = {
    "instagram": {
        "package": "com.instagram.android",
        "activity": "com.instagram.mainactivity.InstagramMainActivity",
        "launch_wait": 4,   # seconds to wait after launch
        "stop_wait": 1,     # seconds to wait after force-stop
    },
    "tiktok": {
        "package": "com.zhiliaoapp.musically",
        "activity": "com.ss.android.ugc.aweme.splash.SplashActivity",
        "launch_wait": 4,
        "stop_wait": 1.5,
    },
}


class AppService:
    """
    Manages a single mobile app (Instagram or TikTok) on a connected device.

    Requires a ConnectionService that is already connected.
    """

    def __init__(self, connection, platform: str = "instagram"):
        """
        Args:
            connection: A connected ConnectionService instance.
            platform: "instagram" or "tiktok".
        """
        if platform not in APPS:
            raise ValueError(f"Unknown platform '{platform}'. Must be one of: {list(APPS.keys())}")

        self._conn = connection
        self._platform = platform
        self._config = APPS[platform]

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
