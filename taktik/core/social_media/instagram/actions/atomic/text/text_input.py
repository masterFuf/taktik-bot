"""Core text input primitives (type, clear, human-like delays)."""

import time
from typing import Optional
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import TEXT_INPUT_SELECTORS, DETECTION_SELECTORS


class TextInputMixin(BaseAction):
    """Mixin: core typing (type_text, human delays, clear field, generic _type_in_field)."""

    def type_text(self, text: str, clear_first: bool = False, human_typing: bool = True) -> bool:
        if not text:
            self.logger.warning("Empty text provided")
            return False
        
        try:
            self.logger.debug(f"⌨️ Typing text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            
            if clear_first:
                self.clear_text_field()
            
            # Use Taktik Keyboard for reliable text input
            if not self._type_with_taktik_keyboard(text):
                self.logger.warning("Taktik Keyboard failed, falling back to send_keys")
                if human_typing:
                    self._type_with_human_delays(text)
                else:
                    self.device.send_keys(text)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during typing: {e}")
            return False
    
    def _type_with_human_delays(self, text: str) -> None:
        """Fallback method using send_keys character by character."""
        for i, char in enumerate(text):
            self.device.send_keys(char)
            
            if i < len(text) - 1:
                delay = self.utils.generate_human_like_delay(0.05, 0.15)
                time.sleep(delay)
    
    def clear_text_field(self) -> bool:
        try:
            self.logger.debug("🗑️ Clearing text field")
            
            self.device.send_keys("", clear=True)
            return True
            
        except Exception as e:
            self.logger.debug(f"Méthode 1 échouée: {e}")
            
            try:
                self.device.press("ctrl+a")
                time.sleep(0.1)
                self.device.press("del")
                return True
                
            except Exception as e2:
                self.logger.error(f"Cannot clear field: {e2}")
                return False

    def _type_in_field(self, text: str, field_selectors: list, field_name: str, emoji: str = "📝") -> bool:
        """
        Generic method to type text in a specific field.
        
        Args:
            text: Text to type
            field_selectors: List of selectors to find the field
            field_name: Name of the field for logging
            emoji: Emoji for logging
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.debug(f"{emoji} Typing {field_name}: '{text[:30]}...'")
        
        if not self._find_and_click(field_selectors, timeout=5):
            self.logger.error(f"Cannot find field {field_name}")
            return False
        
        self._human_like_delay('typing')
        
        return self.type_text(text, clear_first=True, human_typing=True)
