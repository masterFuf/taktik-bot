"""Threads app lifecycle manager.

Mirrors InstagramManager / TikTokManager. Threads ships as a separate
Android app (com.instagram.barcelona) that shares much of its infrastructure
with Instagram but requires its own selectors and activity entry points.
"""

from typing import Optional

from loguru import logger

from taktik.core.shared.platform.social_media_base import SocialMediaBase
from taktik.core.shared.device.manager import DeviceManager
from taktik.core.shared.device.app_inspection import is_app_running


class ThreadsManager(SocialMediaBase):
    PACKAGE_NAME = "com.instagram.barcelona"
    # Resolved from the Threads APK launch intent.
    MAIN_ACTIVITY = "com.instagram.barcelona.mainactivity.BarcelonaMainActivity"

    def __init__(self, device_id: Optional[str] = None):
        super().__init__(device_id)
        self.device_manager = DeviceManager(device_id)

    def _setup_logger(self):
        return logger.bind(module="threads")

    def is_installed(self) -> bool:
        return self.device_manager.is_app_installed(self.PACKAGE_NAME)

    def is_running(self) -> bool:
        # Comparaison exacte : aucun clone n'est declare pour Threads, donc la question est
        # « ce paquet-la est-il devant ». Deleguee malgre tout, pour qu'il n'y ait qu'un endroit
        # ou lire le premier plan.
        if not self.device_manager.connect():
            return False
        return is_app_running(self.device_manager.device, self.PACKAGE_NAME, "threads")

    def launch(self) -> bool:
        self.logger.info("Launching Threads...")
        if not self.is_installed():
            self.logger.error("Threads is not installed on this device.")
            return False
        if not self.device_manager.connect():
            return False
        # Use monkey to resolve the LAUNCHER activity automatically.
        # `am start -n pkg/BarcelonaMainActivity` sometimes falls through to the
        # Play Store AssetBrowserActivity on newer Threads builds — monkey
        # always picks the right exported entry point.
        # Timeout of 30 s prevents the shell call from blocking indefinitely on
        # slow devices / offline ATX agents.
        try:
            self.device_manager.device.shell(
                ["monkey", "-p", self.PACKAGE_NAME, "-c", "android.intent.category.LAUNCHER", "1"],
                timeout=30,
            )
            self.logger.info("Threads launched via monkey")
            return True
        except Exception as e:
            self.logger.warning(f"monkey launch failed ({e}), falling back to launch_app")
            return self.device_manager.launch_app(self.PACKAGE_NAME, self.MAIN_ACTIVITY)

    def stop(self) -> bool:
        self.logger.info("Stopping Threads...")
        return self.device_manager.stop_app(self.PACKAGE_NAME)

    def restart(self) -> bool:
        """Force stop and relaunch Threads for a clean state."""
        import time

        self.logger.info("Restarting Threads (force stop + launch)...")
        self.stop()
        time.sleep(1.5)
        return self.launch()

    def login(self, username: str, password: str) -> bool:
        # TODO: implement UI-driven login once selectors are captured.
        self.logger.info(f"Login attempt for {username} (not yet implemented)")
        return False

    def logout(self) -> bool:
        # TODO: implement UI-driven logout once selectors are captured.
        self.logger.info("Logout requested (not yet implemented)")
        return False
