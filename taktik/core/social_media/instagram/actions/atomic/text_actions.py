from typing import Optional, Dict, Any, List
from loguru import logger
import time

from ..core.base_action import BaseAction
from ...ui.selectors import TEXT_INPUT_SELECTORS, DETECTION_SELECTORS


class TextActions(BaseAction):
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-text-atomic")
        self.text_selectors = TEXT_INPUT_SELECTORS
        self.detection_selectors = DETECTION_SELECTORS
    
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
    
    def type_in_search_bar(self, search_term: str) -> bool:
        self.logger.debug(f"🔍 Typing in search bar: '{search_term}'")
        
        if not self._find_and_click(self.detection_selectors.search_bar_selectors, timeout=5):
            self.logger.error("Cannot find search bar")
            return False
        
        self._human_like_delay('typing')
        
        return self.type_text(search_term, clear_first=True, human_typing=True)
    
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
    
    def type_comment(self, comment_text: str) -> bool:
        """Type a comment in the comment field."""
        return self._type_in_field(comment_text, self.text_selectors.comment_field_selectors, "comment", "💬")
    
    def type_caption(self, caption_text: str) -> bool:
        """Type a caption in the caption field."""
        return self._type_in_field(caption_text, self.text_selectors.caption_field_selectors, "caption", "📝")
    
    def type_bio(self, bio_text: str) -> bool:
        """Type a bio in the bio field."""
        return self._type_in_field(bio_text, self.text_selectors.bio_field_selectors, "bio", "👤")
    
    def send_message(self, message_text: str) -> bool:
        self.logger.debug(f"💌 Sending message: '{message_text[:30]}...'")
        
        if not self._find_and_click(self.text_selectors.message_field_selectors, timeout=5):
            self.logger.error("Cannot find field message")
            return False
        
        self._human_like_delay('typing')
        
        if not self.type_text(message_text, clear_first=True, human_typing=True):
            return False
        
        return self._find_and_click(self.text_selectors.send_button_selectors, timeout=3)
    
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
    
    def validate_text_input(self, expected_text: str, field_selectors: List[str]) -> bool:
        actual_text = self._get_text_from_element(field_selectors)
        
        if actual_text:
            is_valid = expected_text.lower().strip() in actual_text.lower().strip()
            self.logger.debug(f"✅ Text validation: {'OK' if is_valid else 'KO'}")
            return is_valid
        
        return False
