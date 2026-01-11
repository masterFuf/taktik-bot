from taktik.core.social_media.instagram.actions.core.social_media_base import SocialMediaBase
from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
from loguru import logger
from typing import Optional

class TikTokManager(SocialMediaBase):
    PACKAGE_NAME = "com.zhiliaoapp.musically"
    MAIN_ACTIVITY = "com.ss.android.ugc.aweme.splash.SplashActivity"

    def __init__(self, device_id: Optional[str] = None):
        super().__init__(device_id)
        self.device_manager = DeviceManager(device_id)

    def _setup_logger(self):
        return logger.bind(module="tiktok")

    def is_installed(self) -> bool:
        return self.device_manager.is_app_installed(self.PACKAGE_NAME)

    def is_running(self) -> bool:
        if not self.device_manager.connect():
            return False
        try:
            current_app = self.device_manager.device.app_current()
            return current_app['package'] == self.PACKAGE_NAME
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification de TikTok: {e}")
            return False

    def launch(self) -> bool:
        self.logger.info("Lancement de TikTok...")
        if not self.is_installed():
            self.logger.error("TikTok n'est pas installé.")
            return False
        return self.device_manager.launch_app(self.PACKAGE_NAME, self.MAIN_ACTIVITY)

    def stop(self) -> bool:
        self.logger.info("Arrêt de TikTok...")
        return self.device_manager.stop_app(self.PACKAGE_NAME)

    def restart(self) -> bool:
        """Force stop and relaunch TikTok to ensure clean state."""
        self.logger.info("🔄 Restarting TikTok (force stop + launch)...")
        
        # Force stop TikTok
        if self.is_running():
            self.stop()
            import time
            time.sleep(1)  # Wait for app to fully stop
        
        # Launch TikTok fresh
        return self.launch()

    def login(self, username: str, password: str) -> bool:
        # À implémenter: login automatisé via UI
        self.logger.info(f"Tentative de connexion pour {username}")
        return False

    def logout(self) -> bool:
        # À implémenter: logout automatisé via UI
        self.logger.info("Déconnexion en cours...")
        return False
