"""Instagram app management — open, check running, debug screen."""


class AppManagementMixin:
    """Mixin: gestion app Instagram (open, is_open, debug screen)."""

    def _is_instagram_open(self) -> bool:
        try:
            current_app = self.device.app_current()
            return current_app.get('package') == 'com.instagram.android'
        except Exception:
            return False
    
    def _open_instagram(self) -> bool:
        try:
            self.device.app_start('com.instagram.android')
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
