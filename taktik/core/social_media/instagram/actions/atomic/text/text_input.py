"""Core text input primitives (type, clear, the login's pasted rescue)."""

import time
from typing import Optional
from loguru import logger

from ...core.base_action import BaseAction


class TextInputMixin(BaseAction):
    """Mixin: core typing (type_text, clear field, generic _type_in_field)."""

    def type_text(self, text: str, clear_first: bool = False, human_typing: bool = True,
                  paste_if_keyboard_fails: bool = False) -> bool:
        """Type `text` into the focused field through the Taktik Keyboard.

        A keyboard that does not type is a failure: False, said in the log, and nothing written
        another way. Pasting (`adb shell input text`, uiautomator2's `send_keys`) writes the whole
        text at once through another keyboard, a signal no person gives. Only the login asks for
        its rescue (`paste_if_keyboard_fails`, `_paste_when_keyboard_fails`), until Kevin decides.
        `human_typing` only shapes that rescue.
        """
        if not text:
            self.logger.warning("Empty text provided")
            return False

        try:
            # The length only: this types passwords too.
            self.logger.debug(f"⌨️ Typing {len(text)} chars")

            if clear_first:
                self.clear_text_field()

            if self._type_with_taktik_keyboard(text):
                return True
            if paste_if_keyboard_fails:
                return self._paste_when_keyboard_fails(text, human_typing)
            self.logger.error("The Taktik Keyboard did not type the text: not typed, nothing pasted")
            return False

        except Exception as e:
            self.logger.error(f"Error during typing: {e}")
            return False

    def _paste_when_keyboard_fails(self, text: str, human_typing: bool) -> bool:
        """The login's rescue when the Taktik Keyboard did not type, kept as it was: `adb shell
        input text`, then uiautomator2's `send_keys` (the whole text), then `send_keys` letter by
        letter. Each writes through another keyboard than the bot's; every other text fails
        instead (`type_text`). Unverified, as before: True once one of them ran."""
        self.logger.warning("Taktik Keyboard failed: the login's text is pasted (adb input text)")
        try:
            if self._adb_input_text(text):
                return True
            self.device.send_keys(text)
            return True
        except Exception as exc:
            self.logger.warning(f"send_keys failed ({exc}): typing letter by letter with send_keys")
        if human_typing:
            self._type_with_human_delays(text)
        else:
            self.device.send_keys(text)
        return True

    def _type_with_human_delays(self, text: str) -> None:
        """The login's last rescue: send_keys character by character."""
        for i, char in enumerate(text):
            self.device.send_keys(char)
            
            if i < len(text) - 1:
                delay = self.utils.generate_human_like_delay(0.05, 0.15)
                time.sleep(delay)
    
    def clear_text_field(self) -> bool:
        self.logger.debug("🗑️ Clearing text field")
        
        # Select-all is a key chord the device cannot press, and a lone delete would only eat
        # the last characters: clear through the keyboard the text is then typed with.
        if self._clear_text_with_taktik_keyboard():
            return True

        # Fallback: uiautomator2 clear
        try:
            self.device.send_keys("", clear=True)
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
        self.logger.debug(f"{emoji} Typing {field_name} ({len(text)} chars)")

        # Before the tap: a keyboard switched after it can cost the field its focus.
        self._ensure_taktik_keyboard()
        if not self._find_and_click(field_selectors, timeout=5):
            self.logger.error(f"Cannot find field {field_name}")
            return False
        
        self._human_like_delay('typing')
        
        return self.type_text(text, clear_first=True, human_typing=True)
