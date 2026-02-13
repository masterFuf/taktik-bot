"""Keyboard control actions (enter, backspace, hide, paste, select, clipboard)."""

import time
from typing import Optional
from loguru import logger

from ...core.base_action import BaseAction


class KeyboardControlMixin(BaseAction):
    """Mixin: keyboard keys (enter, backspace), hide keyboard, clipboard (paste, select all)."""

    def press_enter(self) -> bool:
        try:
            self.logger.debug("⏎ Pressing Enter")
            self.device.press("enter")
            self._human_like_delay('typing')
            return True
        except Exception as e:
            self.logger.error(f"Error pressing Enter: {e}")
            return False
    
    def press_backspace(self, count: int = 1) -> bool:
        try:
            self.logger.debug(f"⌫ Pressing Backspace ({count}x)")
            for _ in range(count):
                self.device.press("del")
                if count > 1:
                    time.sleep(0.1)
            self._human_like_delay('typing')
            return True
        except Exception as e:
            self.logger.error(f"Error pressing Backspace: {e}")
            return False
    
    def hide_keyboard(self) -> bool:
        try:
            self.logger.debug("⌨️ Hiding keyboard")
            
            self.device.press("back")
            self._human_like_delay('typing')
            return True
            
        except Exception as e:
            self.logger.debug(f"Method 1 failed: {e}")
            
            try:
                center_x = self.device.info['displayWidth'] // 2
                center_y = self.device.info['displayHeight'] // 2
                self.device.click(center_x, center_y)
                self._human_like_delay('typing')
                return True
                
            except Exception as e2:
                self.logger.error(f"Cannot hide keyboard: {e2}")
                return False
    
    def paste_text(self, text: str = None) -> bool:
        try:
            if text:
                self.logger.debug(f"📋 Pasting text: '{text[:30]}...'")
                return self.type_text(text)
            else:
                self.logger.debug("📋 Pasting from clipboard")
                self.device.press("ctrl+v")
                self._human_like_delay('typing')
                return True
                
        except Exception as e:
            self.logger.error(f"Error during paste: {e}")
            return False
    
    def select_all_text(self) -> bool:
        try:
            self.logger.debug("🔤 Selecting all text")
            self.device.press("ctrl+a")
            self._human_like_delay('typing')
            return True
        except Exception as e:
            self.logger.error(f"Error selecting text: {e}")
            return False
    
    def get_text_from_active_field(self) -> Optional[str]:
        try:
            self.select_all_text()
            return None
            
        except Exception as e:
            self.logger.error(f"Error retrieving text: {e}")
            return None
