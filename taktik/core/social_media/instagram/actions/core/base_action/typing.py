"""Text input — character-by-character human simulation + Taktik Keyboard management."""

import time
import random
import base64


class TypingMixin:
    """Mixin: saisie texte humaine + gestion Taktik Keyboard avec fallback send_keys."""

    def _type_like_human(self, text: str, min_delay: float = 0.05, max_delay: float = 0.15) -> None:
        """
        Tape du texte caractère par caractère avec des délais humains.
        Simule une frappe naturelle avec des variations de vitesse.
        
        Args:
            text: Le texte à taper
            min_delay: Délai minimum entre les caractères (en secondes)
            max_delay: Délai maximum entre les caractères (en secondes)
        """
        self.logger.debug(f"⌨️ Typing '{text}' with human-like delays")
        
        for i, char in enumerate(text):
            # Taper le caractère
            self.device.send_keys(char)
            
            # Délai variable entre les caractères
            # Plus rapide pour les caractères consécutifs similaires
            if i > 0 and text[i-1].lower() == char.lower():
                # Même touche = plus rapide
                delay = random.uniform(min_delay * 0.5, max_delay * 0.7)
            elif char in '._-':
                # Caractères spéciaux = légèrement plus lent (changement de zone clavier)
                delay = random.uniform(min_delay * 1.2, max_delay * 1.5)
            else:
                # Délai normal avec distribution gaussienne
                mean = (min_delay + max_delay) / 2
                std = (max_delay - min_delay) / 4
                delay = max(min_delay, min(max_delay, random.gauss(mean, std)))
            
            # Occasionnellement, une micro-pause (comme si on cherchait la touche)
            if random.random() < 0.08:  # 8% de chance
                delay += random.uniform(0.1, 0.3)
            
            time.sleep(delay)
        
        self.logger.debug(f"✅ Finished typing '{text}'")

    def _is_taktik_keyboard_active(self) -> bool:
        """Check if Taktik Keyboard (ADB Keyboard) is the active IME."""
        try:
            device_serial = self._get_device_serial()
            result = self._run_adb_shell(device_serial, 'settings get secure default_input_method')
            return self._TAKTIK_KEYBOARD_IME in result
        except Exception as e:
            self.logger.debug(f"Cannot check keyboard status: {e}")
            return False
    
    def _activate_taktik_keyboard(self) -> bool:
        """Activate Taktik Keyboard as the default IME."""
        try:
            device_serial = self._get_device_serial()
            
            # Enable the IME
            self._run_adb_shell(device_serial, f'ime enable {self._TAKTIK_KEYBOARD_IME}')
            
            # Set as default
            result = self._run_adb_shell(device_serial, f'ime set {self._TAKTIK_KEYBOARD_IME}')
            
            if 'selected' in result.lower():
                self.logger.debug("✅ Taktik Keyboard activated")
                return True
            else:
                self.logger.warning(f"⚠️ Failed to activate Taktik Keyboard: {result}")
                return False
                
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
            self.logger.debug(f"⌨️ Typed via adb input text: '{text[:20]}...'")
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
            device_serial = self._get_device_serial()
            
            # Check if Taktik Keyboard is active, activate if not
            if not self._is_taktik_keyboard_active():
                self.logger.debug("Taktik Keyboard not active, activating...")
                if not self._activate_taktik_keyboard():
                    self.logger.warning("⚠️ Could not activate Taktik Keyboard, trying adb input text")
                    if self._adb_input_text(text):
                        return True
                    self.device.send_keys(text)
                    return True
            
            # Encode text as base64
            text_b64 = base64.b64encode(text.encode('utf-8')).decode('utf-8')
            
            # Send broadcast with text
            broadcast_cmd = f'am broadcast -a {self._IME_MESSAGE_B64} --es msg {text_b64} --ei delay_mean {delay_mean} --ei delay_deviation {delay_deviation}'
            result = self._run_adb_shell(device_serial, broadcast_cmd)
            
            if result and 'error' not in result.lower():
                # Wait for typing to complete
                typing_time = (delay_mean * len(text) + delay_deviation) / 1000
                self.logger.debug(f"⌨️ Taktik Keyboard typing '{text[:20]}...' ({typing_time:.1f}s)")
                time.sleep(typing_time + 0.5)  # Add small buffer
                return True
            else:
                self.logger.warning(f"⚠️ Taktik Keyboard broadcast failed: {result}")
                # Fallback: adb input text, then send_keys
                if self._adb_input_text(text):
                    return True
                self.device.send_keys(text)
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Error using Taktik Keyboard: {e}")
            try:
                if self._adb_input_text(text):
                    return True
                self.device.send_keys(text)
                return True
            except:
                return False
