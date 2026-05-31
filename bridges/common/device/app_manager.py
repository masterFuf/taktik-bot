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
    "threads": {
        "package": "com.instagram.barcelona",
        "activity": "com.instagram.barcelona.mainactivity.BarcelonaMainActivity",
        "launch_wait": 4,
        "stop_wait": 1,
    },
    "gmail": {
        "package": "com.google.android.gm",
        "activity": "com.google.android.gm.ui.MailActivityGmail",
        "launch_wait": 3,
        "stop_wait": 1,
    },
    "youtube": {
        "package": "com.google.android.youtube",
        "activity": "com.google.android.youtube.app.honeycomb.Shell$HomeActivity",
        "launch_wait": 4,
        "stop_wait": 1,
    },
}


# Alternative package names for the same platform
# (same app shipped under different package IDs in different regions)
PLATFORM_ALTERNATIVES = {
    "tiktok": [
        "com.zhiliaoapp.musically",   # TikTok musical.ly (default)
        "com.ss.android.ugc.trill",   # TikTok global
        "com.ss.android.ugc.aweme",   # TikTok (China / Douyin)
    ],
}


def force_stop_app(device_id: str, platform: str) -> bool:
    """
    Force-stop a platform app on the given device using ADB.

    Does NOT require an active uiautomator2 connection — safe to call
    at any point (e.g. inside a finally block after the workflow ends).

    For TikTok, tries all known package alternatives if the default fails.

    Args:
        device_id: ADB device serial.
        platform: Platform key ("instagram", "tiktok", "threads", "gmail", "youtube").

    Returns:
        True if at least one force-stop command succeeded, False otherwise.
    """
    config = APPS.get(platform)
    if not config:
        logger.warning(f"[AppService] Unknown platform '{platform}' for force-stop")
        return False

    packages_to_try = [config["package"]]
    if platform in PLATFORM_ALTERNATIVES:
        # Include all known alternatives so we hit the right package regardless
        # of which variant is installed on this device.
        for alt in PLATFORM_ALTERNATIVES[platform]:
            if alt not in packages_to_try:
                packages_to_try.append(alt)

    success = False
    for pkg in packages_to_try:
        try:
            result = subprocess.run(
                ["adb", "-s", device_id, "shell", "am", "force-stop", pkg],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                logger.info(f"[AppService] Closed {platform} ({pkg}) on {device_id}")
                success = True
                break
        except Exception as e:
            logger.warning(f"[AppService] Could not force-stop {platform} ({pkg}): {e}")

    if not success:
        logger.warning(f"[AppService] force_stop_app failed for {platform} on {device_id}")
    return success


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
        if platform not in APPS:
            raise ValueError(f"Unknown platform '{platform}'. Must be one of: {list(APPS.keys())}")

        self._conn = connection
        self._platform = platform
        # Copy config so we don't mutate the shared APPS dict
        self._config = dict(APPS[platform])

        if package_override and package_override != self._config["package"]:
            logger.info(f"[AppService] Using clone package: {package_override}")
            self._config["package"] = package_override
            # Taktik-cloner packages (com.taktik.ig*, com.taktik.tk*) don't share
            # the same internal activity class, so skip explicit activity launch.
            # NomixCloner preserves the original activity class, so it's fine.
            if package_override.startswith("com.taktik."):
                self._config["activity"] = None
        elif not package_override and platform in PLATFORM_ALTERNATIVES:
            # Auto-detect: if the default package is not installed, try alternatives
            # (e.g. com.ss.android.ugc.trill when com.zhiliaoapp.musically is absent)
            dm = connection.device_manager
            if dm is not None:
                alternatives = PLATFORM_ALTERNATIVES[platform]
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
