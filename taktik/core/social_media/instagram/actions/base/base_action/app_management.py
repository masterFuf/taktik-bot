"""Instagram app management — open, check running, debug screen."""

from taktik.core.clone import get_active_package
from taktik.core.shared.device.app_inspection import is_app_running


class AppManagementMixin:
    """Mixin: gestion app Instagram (open, is_open, debug screen)."""

    def _is_instagram_open(self) -> bool:
        # Delegue a la primitive partagee : le meme fait etait etabli de cinq facons, et deux
        # d'entre elles avaient deja diverge (voir `InstagramManager.is_running`).
        return is_app_running(self.device, get_active_package(), "instagram")
    
    def _open_instagram(self) -> bool:
        try:
            pkg = get_active_package()
            if pkg.startswith('com.taktik.'):
                self.device.shell(['am', 'start', '-n',
                                   f'{pkg}/com.instagram.mainactivity.LauncherActivity'])
            else:
                self.device.app_start(pkg)
            self._human_like_delay('navigation')
            return self._is_instagram_open()
        except Exception as e:
            self.logger.error(f"Error opening Instagram: {e}")
            return False
    
    def _debug_current_screen(self, description: str = "") -> None:
        try:
            current_app = self.device.app_current()
            activity = current_app.get('activity', 'Unknown')
            
            self.logger.debug(f"🔍 Debug screen {description}")
            self.logger.debug(f"📱 Activity: {activity}")
            self.logger.debug(f"📊 Stats: {self._method_stats}")
        except Exception as e:
            self.logger.debug(f"Debug error: {e}")

    def _press_back(self, count: int = 1) -> None:
        for _ in range(count):
            self.device.press('back')
            self._human_like_delay('click')
