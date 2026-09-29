from taktik.core.clone import get_active_package
from taktik.core.shared.device.app_inspection import is_app_running
from taktik.core.shared.platform.social_media_base import SocialMediaBase
from taktik.core.shared.device.manager import DeviceManager
from loguru import logger
from typing import Optional

class InstagramManager(SocialMediaBase):
    PACKAGE_NAME = "com.instagram.android"
    MAIN_ACTIVITY = "com.instagram.mainactivity.InstagramMainActivity"

    def __init__(self, device_id: Optional[str] = None):
        super().__init__(device_id)
        self.device_manager = DeviceManager(device_id)

    def _setup_logger(self):
        return logger.bind(module="instagram")

    def is_installed(self) -> bool:
        return self.device_manager.is_app_installed(self.PACKAGE_NAME)

    def is_running(self) -> bool:
        """Instagram est-il au premier plan ?

        Compare au paquet **actif**, pas a la constante officielle. Sur un appareil ou le clone est
        le paquet utilise, comparer a `PACKAGE_NAME` rendait `False` alors qu'Instagram etait bien
        a l'ecran — et la meme question, posee cent lignes plus loin par `AppManagementMixin`,
        rendait `True`. Deux controles du meme fait qui se contredisaient.

        Hors run, `get_active_package()` vaut le paquet officiel : le comportement est alors
        exactement celui d'avant.
        """
        if not self.device_manager.connect():
            return False
        return is_app_running(self.device_manager.device, get_active_package(), "instagram")

    def launch(self) -> bool:
        self.logger.info("Lancement d'Instagram...")
        if not self.is_installed():
            self.logger.error("Instagram n'est pas installé.")
            return False
        return self.device_manager.launch_app(self.PACKAGE_NAME, self.MAIN_ACTIVITY)

    def stop(self) -> bool:
        self.logger.info("Arrêt d'Instagram...")
        return self.device_manager.stop_app(self.PACKAGE_NAME)

    def login(self, username: str, password: str) -> bool:
        # À implémenter: login automatisé via UI
        self.logger.info(f"Tentative de connexion pour {username}")
        return False

    def logout(self) -> bool:
        # À implémenter: logout automatisé via UI
        self.logger.info("Déconnexion en cours...")
        return False
