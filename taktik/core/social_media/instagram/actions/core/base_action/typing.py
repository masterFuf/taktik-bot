"""Text input — character-by-character human simulation + Taktik Keyboard management."""

import time
import random

from taktik.core.shared.behavior.sampling import sample_within


class TypingMixin:
    """Mixin: human text entry, through the dedicated keyboard with a fallback."""

    def _type_like_human(self, text: str, min_delay: float = 0.05, max_delay: float = 0.15) -> None:
        """
        Type text character by character, with human delays.
        Reproduces a natural typing rhythm, with speed variations.
        
        Args:
            text: the text to type
            min_delay: minimum delay between characters, in seconds
            max_delay: maximum delay between characters, in seconds
        """
        self.logger.debug(f"⌨️ Typing {len(text)} chars with human-like delays")
        
        for i, char in enumerate(text):
            # Type the character
            self.device.send_keys(char)
            
            # Variable delay between characters
            # Faster on consecutive similar characters
            if i > 0 and text[i-1].lower() == char.lower():
                # Same key: faster
                delay = random.uniform(min_delay * 0.5, max_delay * 0.7)
            elif char in '._-':
                # Special characters: slightly slower, since the keyboard area changes
                delay = random.uniform(min_delay * 1.2, max_delay * 1.5)
            else:
                # Normal delay, on a gaussian distribution truncated to the range by redrawing
                mean = (min_delay + max_delay) / 2
                std = (max_delay - min_delay) / 4
                delay = sample_within(lambda: random.gauss(mean, std), min_delay, max_delay)
            
            # Occasionally a micro-pause, as if looking for the key
            if random.random() < 0.08:  # 8% de chance
                delay += random.uniform(0.1, 0.3)
            
            time.sleep(delay)
        
        self.logger.debug(f"✅ Finished typing {len(text)} chars")

    def _is_taktik_keyboard_active(self) -> bool:
        """Check if Taktik Keyboard (ADB Keyboard) is the active IME, through the shared owner
        (which also remembers the phone's own keyboard, to give it back at the end)."""
        try:
            from taktik.core.shared.input.taktik_keyboard import is_taktik_keyboard_active

            return is_taktik_keyboard_active(self._get_device_serial())
        except Exception as e:
            self.logger.debug(f"Cannot check keyboard status: {e}")
            return False
    
    def _activate_taktik_keyboard(self) -> bool:
        """Activate Taktik Keyboard as the default IME, through the shared owner.

        It used to run its own `ime set`, a second switch that remembered nothing: the phone's
        keyboard is now remembered and given back at the end of the session in ONE place
        (`taktik.core.shared.input.taktik_keyboard`).
        """
        try:
            from taktik.core.shared.input.taktik_keyboard import activate_taktik_keyboard

            return activate_taktik_keyboard(self._get_device_serial())
        except Exception as e:
            self.logger.error(f"❌ Error activating Taktik Keyboard: {e}")
            return False
    
    def _adb_input_text(self, text: str) -> bool:
        """Last-resort fallback: type text via 'adb shell input text'.
        
        Only supports ASCII and replaces spaces with %s (ADB convention).
        """
        try:
            device_serial = self._get_device_serial()
            safe_text = text.replace(' ', '%s').replace("'", "\\'").replace('"', '\\"')
            self._run_adb_shell(device_serial, f'input text "{safe_text}"')
            self.logger.debug(f"⌨️ Typed via adb input text ({len(text)} chars)")
            return True
        except Exception as e:
            self.logger.error(f"❌ adb input text failed: {e}")
            return False

    def _type_with_taktik_keyboard(self, text: str, delay_mean: int = 80, delay_deviation: int = 30) -> bool:
        """
        Type text using Taktik Keyboard (ADB Keyboard) via broadcast.
        This is more reliable than uiautomator2's send_keys for special characters.
        
        Fallback chain:
        1. Taktik Keyboard broadcast (ADB_INPUT_B64)
        2. adb shell input text (direct ADB, ASCII only)
        3. uiautomator2 send_keys (last resort)
        
        Args:
            text: Text to type
            delay_mean: Mean delay between characters in ms (default 80)
            delay_deviation: Delay deviation in ms (default 30)
            
        Returns:
            True if successful, False otherwise
        """
        if not text:
            return True

        try:
            from taktik.core.shared.input.taktik_keyboard import type_with_taktik_keyboard

            # The shared owner activates the keyboard, broadcasts and waits out the typing.
            if type_with_taktik_keyboard(self._get_device_serial(), text, delay_mean, delay_deviation):
                return True
            self.logger.warning("⚠️ Taktik Keyboard failed, trying adb input text")
        except Exception as e:
            self.logger.error(f"❌ Error using Taktik Keyboard: {e}")
        try:
            if self._adb_input_text(text):
                return True
            self.device.send_keys(text)
            return True
        except Exception:
            return False
