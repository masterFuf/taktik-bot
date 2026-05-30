from typing import Optional

from loguru import logger

from taktik.core.shared.device.manager import DeviceManager
from taktik.core.shared.platform.social_media_base import SocialMediaBase

# All known TikTok package names, in order of preference.
TIKTOK_PACKAGES = [
    "com.zhiliaoapp.musically",   # TikTok international
    "com.ss.android.ugc.trill",   # TikTok Trill (some regions / older installs)
    "com.ss.android.ugc.aweme",   # Douyin (China)
]

TIKTOK_MAIN_ACTIVITY = "com.ss.android.ugc.aweme.splash.SplashActivity"


class TikTokManager(SocialMediaBase):
    # Legacy class constant kept for backward compat (upload_workflow etc.)
    PACKAGE_NAME = "com.zhiliaoapp.musically"
    MAIN_ACTIVITY = TIKTOK_MAIN_ACTIVITY

    def __init__(self, device_id: Optional[str] = None):
        super().__init__(device_id)
        self.device_manager = DeviceManager(device_id)
        self._detected_package: Optional[str] = None

    def _setup_logger(self):
        return logger.bind(module="tiktok")

    def _resolve_package(self) -> Optional[str]:
        """Detect which TikTok package is installed on this device.

        Result is cached after the first successful detection so we
        don't hit ADB on every call.
        """
        if self._detected_package:
            return self._detected_package

        for pkg in TIKTOK_PACKAGES:
            if self.device_manager.is_app_installed(pkg):
                self._detected_package = pkg
                if pkg != "com.zhiliaoapp.musically":
                    self.logger.info(f"📦 TikTok variant detected: {pkg}")
                return pkg

        self.logger.error(
            f"No TikTok package found on device {self.device_manager.device_id}. "
            f"Tried: {', '.join(TIKTOK_PACKAGES)}"
        )
        return None

    @property
    def package_name(self) -> str:
        """Return the installed TikTok package name (auto-detected)."""
        return self._resolve_package() or "com.zhiliaoapp.musically"

    def is_installed(self) -> bool:
        return self._resolve_package() is not None

    def is_running(self) -> bool:
        if not self.device_manager.connect():
            return False
        try:
            current_app = self.device_manager.device.app_current()
            return current_app["package"] in TIKTOK_PACKAGES
        except Exception as e:
            self.logger.error(f"Erreur lors de la verification de TikTok: {e}")
            return False

    def launch(self) -> bool:
        self.logger.info("Lancement de TikTok...")
        pkg = self._resolve_package()
        if not pkg:
            self.logger.error("TikTok n est pas installe.")
            return False
        return self.device_manager.launch_app(pkg, TIKTOK_MAIN_ACTIVITY)

    def stop(self) -> bool:
        self.logger.info("Arret de TikTok...")
        # Use cached package to avoid 3 ADB round-trips on every stop/restart
        pkg = self._detected_package or self._resolve_package()
        if pkg:
            self.device_manager.stop_app(pkg)
            return True
        # Fallback: stop all known packages (first run before _resolve_package was called)
        stopped = False
        for p in TIKTOK_PACKAGES:
            if self.device_manager.is_app_installed(p):
                self.device_manager.stop_app(p)
                stopped = True
        return stopped

    def restart(self) -> bool:
        """Force stop and relaunch TikTok to ensure clean state."""
        self.logger.info("Restarting TikTok (force stop + launch)...")

        import time

        pkg = self._resolve_package()
        if not pkg:
            self.logger.error("Cannot restart: no TikTok package found on device.")
            return False

        self.stop()
        time.sleep(1.5)

        if not self.device_manager.connect():
            return False

        try:
            self.device_manager.device.app_start(
                pkg,
                TIKTOK_MAIN_ACTIVITY,
                stop=True,
            )
            self.logger.info("TikTok launched with clean state")
            return True
        except Exception as e:
            self.logger.error(f"Failed to restart TikTok: {e}")
            return False

    def login(self, username: str, password: str) -> bool:
        self.logger.info(f"Tentative de connexion pour {username}")
        return False

    def logout(self) -> bool:
        self.logger.info("Deconnexion en cours...")
        return False
