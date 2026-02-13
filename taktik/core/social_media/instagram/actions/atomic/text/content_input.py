"""Domain-specific text input (comment, caption, bio, search, message)."""

from typing import Optional
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import TEXT_INPUT_SELECTORS, DETECTION_SELECTORS


class ContentInputMixin(BaseAction):
    """Mixin: domain-specific field inputs (comment, caption, bio, search bar, DM)."""

    def type_in_search_bar(self, search_term: str) -> bool:
        self.logger.debug(f"🔍 Typing in search bar: '{search_term}'")
        
        if not self._find_and_click(self.detection_selectors.search_bar_selectors, timeout=5):
            self.logger.error("Cannot find search bar")
            return False
        
        self._human_like_delay('typing')
        
        return self.type_text(search_term, clear_first=True, human_typing=True)

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

    def validate_text_input(self, expected_text: str, field_selectors: list) -> bool:
        actual_text = self._get_text_from_element(field_selectors)
        
        if actual_text:
            is_valid = expected_text.lower().strip() in actual_text.lower().strip()
            self.logger.debug(f"✅ Text validation: {'OK' if is_valid else 'KO'}")
            return is_valid
        
        return False
