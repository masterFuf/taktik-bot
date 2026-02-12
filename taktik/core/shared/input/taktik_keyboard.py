"""
Taktik Keyboard Utility Module (Shared)

Provides functions to type text using the Taktik Keyboard (ADB Keyboard)
via ADB broadcasts. This is more reliable than uiautomator2's send_keys
for special characters, emojis, and non-ASCII text.

Shared between Instagram and TikTok modules.
"""

import base64
import subprocess
import time
from loguru import logger


# Taktik Keyboard constants (ADB Keyboard)
TAKTIK_KEYBOARD_PKG = 'com.alexal1.adbkeyboard'
TAKTIK_KEYBOARD_IME = 'com.alexal1.adbkeyboard/.AdbIME'
IME_MESSAGE_B64 = 'ADB_INPUT_B64'
IME_CLEAR_TEXT = 'ADB_CLEAR_TEXT'


def run_adb_shell(device_id: str, command: str) -> str:
    """
    Execute an ADB shell command using adbutils (preferred) or subprocess fallback.
    This ensures compatibility with packaged builds where ADB may not be in PATH.
    
    Args:
        device_id: ADB device serial/ID
        command: Shell command to execute (without 'adb shell' prefix)
        
    Returns:
        Command output as string, or empty string on error
    """
    try:
        from adbutils import adb
        device = adb.device(serial=device_id)
        return device.shell(command)
    except ImportError:
        # Fallback to subprocess if adbutils not available
        try:
            result = subprocess.run(
                ['adb', '-s', device_id, 'shell'] + command.split(),
                capture_output=True, text=True, timeout=10
            )
            return result.stdout if result.returncode == 0 else ''
        except Exception as e:
            logger.debug(f"ADB subprocess error: {e}")
            return ''
    except Exception as e:
        logger.debug(f"ADB shell error: {e}")
        return ''


def is_taktik_keyboard_active(device_id: str) -> bool:
    """Check if Taktik Keyboard (ADB Keyboard) is the active IME."""
    try:
        result = run_adb_shell(device_id, 'settings get secure default_input_method')
        return TAKTIK_KEYBOARD_IME in result
    except Exception as e:
        logger.debug(f"Cannot check keyboard status: {e}")
        return False


def activate_taktik_keyboard(device_id: str) -> bool:
    """Activate Taktik Keyboard as the default IME."""
    try:
        # Enable the IME
        run_adb_shell(device_id, f'ime enable {TAKTIK_KEYBOARD_IME}')
        
        # Set as default
        result = run_adb_shell(device_id, f'ime set {TAKTIK_KEYBOARD_IME}')
        
        if 'selected' in result.lower():
            logger.debug("✅ Taktik Keyboard activated")
            return True
        else:
            logger.warning(f"⚠️ Failed to activate Taktik Keyboard: {result}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error activating Taktik Keyboard: {e}")
        return False


def type_with_taktik_keyboard(device_id: str, text: str, delay_mean: int = 80, delay_deviation: int = 30) -> bool:
    """
    Type text using Taktik Keyboard (ADB Keyboard) via broadcast.
    This is more reliable than uiautomator2's send_keys for special characters.
    
    Args:
        device_id: ADB device serial/ID
        text: Text to type
        delay_mean: Mean delay between characters in ms (default 80)
        delay_deviation: Delay deviation in ms (default 30)
        
    Returns:
        True if successful, False otherwise
    """
    if not text:
        return True
    
    try:
        # Check if Taktik Keyboard is active, activate if not
        if not is_taktik_keyboard_active(device_id):
            logger.debug("Taktik Keyboard not active, activating...")
            if not activate_taktik_keyboard(device_id):
                logger.warning("⚠️ Could not activate Taktik Keyboard")
                return False
        
        # Encode text as base64
        text_b64 = base64.b64encode(text.encode('utf-8')).decode('utf-8')
        
        # Send broadcast with text
        broadcast_cmd = f'am broadcast -a {IME_MESSAGE_B64} --es msg {text_b64} --ei delay_mean {delay_mean} --ei delay_deviation {delay_deviation}'
        result = run_adb_shell(device_id, broadcast_cmd)
        
        if result and 'error' not in result.lower():
            # Wait for typing to complete
            typing_time = (delay_mean * len(text) + delay_deviation) / 1000
            logger.debug(f"⌨️ Taktik Keyboard typing '{text[:20]}...' ({typing_time:.1f}s)")
            time.sleep(typing_time + 0.5)  # Add small buffer
            return True
        else:
            logger.warning(f"⚠️ Taktik Keyboard broadcast failed: {result}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error using Taktik Keyboard: {e}")
        return False


def clear_text_with_taktik_keyboard(device_id: str) -> bool:
    """Clear the current text field using Taktik Keyboard."""
    try:
        result = run_adb_shell(device_id, f'am broadcast -a {IME_CLEAR_TEXT}')
        return bool(result) and 'error' not in result.lower()
    except Exception as e:
        logger.error(f"Error clearing text: {e}")
        return False
