"""
KeyboardService — type text on Android devices via Taktik Keyboard (ADB Keyboard).

Centralizes the keyboard typing logic that was copy-pasted in cold_dm_bridge,
dm_bridge, and smart_comment_bridge.

Usage:
    from bridges.common.keyboard import KeyboardService

    kb = KeyboardService("DEVICE_SERIAL")
    kb.type_text("Hello world! 🚀")
    kb.type_text("Slow typing", delay_mean=120, delay_deviation=40)
"""

import base64
import subprocess
import time
from loguru import logger


# Taktik Keyboard (ADB Keyboard) constants
TAKTIK_KEYBOARD_IME = 'com.alexal1.adbkeyboard/.AdbIME'
IME_MESSAGE_B64 = 'ADB_INPUT_B64'


class KeyboardService:
    """
    Type text on an Android device using Taktik Keyboard (ADB Keyboard).

    This method is more reliable than uiautomator2's send_keys() for
    special characters, accented characters, and emojis.
    """

    def __init__(self, device_id: str):
        self.device_id = device_id

    def ensure_active(self) -> bool:
        """
        Ensure Taktik Keyboard is the active IME.
        Returns True if the keyboard is active (or was successfully activated).
        """
        try:
            result = subprocess.run(
                ['adb', '-s', self.device_id, 'shell', 'settings', 'get', 'secure', 'default_input_method'],
                capture_output=True, text=True, timeout=5
            )

            if TAKTIK_KEYBOARD_IME in result.stdout:
                return True

            # Enable and set Taktik Keyboard
            subprocess.run(
                ['adb', '-s', self.device_id, 'shell', 'ime', 'enable', TAKTIK_KEYBOARD_IME],
                capture_output=True, text=True, timeout=5
            )
            activate_result = subprocess.run(
                ['adb', '-s', self.device_id, 'shell', 'ime', 'set', TAKTIK_KEYBOARD_IME],
                capture_output=True, text=True, timeout=5
            )

            if 'selected' not in activate_result.stdout.lower():
                logger.warning("Could not activate Taktik Keyboard")
                return False

            logger.info("Taktik Keyboard activated")
            return True

        except Exception as e:
            logger.error(f"Error checking/activating Taktik Keyboard: {e}")
            return False

    def type_text(self, text: str, delay_mean: int = 80, delay_deviation: int = 30) -> bool:
        """
        Type text using Taktik Keyboard via ADB broadcast.

        Args:
            text: The text to type (supports Unicode, emojis, accents).
            delay_mean: Average delay between keystrokes in ms.
            delay_deviation: Random deviation around the mean in ms.

        Returns:
            True if the broadcast was sent successfully.
        """
        if not text:
            return True

        try:
            # Ensure keyboard is active
            if not self.ensure_active():
                return False

            # Encode text as base64
            text_b64 = base64.b64encode(text.encode('utf-8')).decode('utf-8')

            # Send broadcast
            cmd = [
                'adb', '-s', self.device_id, 'shell', 'am', 'broadcast',
                '-a', IME_MESSAGE_B64,
                '--es', 'msg', text_b64,
                '--ei', 'delay_mean', str(delay_mean),
                '--ei', 'delay_deviation', str(delay_deviation),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                # Wait for typing to complete
                typing_time = (delay_mean * len(text) + delay_deviation) / 1000
                logger.debug(f"Taktik Keyboard typing '{text[:20]}...' ({typing_time:.1f}s)")
                time.sleep(typing_time + 0.5)
                return True
            else:
                logger.warning(f"Taktik Keyboard broadcast failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error using Taktik Keyboard: {e}")
            return False
