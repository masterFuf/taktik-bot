import time
import random
import os
import re
import base64
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union
from loguru import logger

from .device_facade import DeviceFacade
from .utils import ActionUtils

# Taktik Keyboard constants (ADB Keyboard)
TAKTIK_KEYBOARD_PKG = 'com.alexal1.adbkeyboard'
TAKTIK_KEYBOARD_IME = 'com.alexal1.adbkeyboard/.AdbIME'
IME_MESSAGE_B64 = 'ADB_INPUT_B64'
IME_CLEAR_TEXT = 'ADB_CLEAR_TEXT'


def run_adb_shell(device_id: str, command: str) -> str:
    """
    Execute an ADB shell command using adbutils.
    
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
    except Exception as e:
        logger.debug(f"ADB shell error: {e}")
        return ''


class BaseAction:
    """Base class for all TikTok actions with common functionality."""
    
    def __init__(self, device):
        self.device = device if isinstance(device, DeviceFacade) else DeviceFacade(device)
        self.logger = logger.bind(module=f"tiktok.actions.{self.__class__.__name__.lower()}")
        self.utils = ActionUtils()
        
        self._method_stats = {
            'clicks': 0,
            'waits': 0,
            'sleeps': 0,
            'errors': 0
        }
        
    def _random_sleep(self, min_delay: float = 0.3, max_delay: float = 0.8) -> None:
        """Sleep for a random duration."""
        delay = random.uniform(min_delay, max_delay)
        self.logger.debug(f"⏱️ Random sleep: {delay:.2f}s")
        time.sleep(delay)
    
    def _human_like_delay(self, action_type: str = 'general') -> None:
        """Add human-like delay based on action type."""
        delays = {
            'click': (0.2, 0.5),      
            'navigation': (0.7, 1.5),  
            'scroll': (0.3, 0.7),      
            'typing': (0.08, 0.15),    
            'video_watch': (2.0, 5.0),  # TikTok specific: watch video
            'default': (0.3, 0.8)      
        }
        
        min_delay, max_delay = delays.get(action_type, delays['default'])
        self._random_sleep(min_delay, max_delay)
    
    def _find_and_click(self, selectors: Union[List[str], str], timeout: float = 5.0, 
                       human_delay: bool = True) -> bool:
        """Find element using selectors and click it."""
        if isinstance(selectors, str):
            selectors = [selectors]
        
        start_time = time.time()
        last_error = None
        
        self.logger.debug(f"🔍 Searching for elements with {len(selectors)} selectors")
        
        while time.time() - start_time < timeout:
            for i, selector in enumerate(selectors):
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        self.logger.debug(f"✅ Element found with selector #{i+1}: {selector[:50]}...")
                        element.click()
                        self._method_stats['clicks'] += 1
                        
                        if human_delay:
                            self._human_like_delay('click')
                        
                        return True
                except Exception as e:
                    last_error = e
                    self.logger.debug(f"❌ Selector #{i+1} failed: {str(e)[:100]}")
                    continue
            
            time.sleep(0.5)
        
        self.logger.warning(f"🚫 No element found after {timeout}s")
        if last_error:
            self.logger.debug(f"Last error: {last_error}")
        
        self._method_stats['errors'] += 1
        return False
    
    def _wait_for_element(self, selectors: Union[List[str], str], timeout: float = 10.0, 
                         check_interval: float = 0.5, silent: bool = False) -> bool:
        """Wait for element to appear."""
        if isinstance(selectors, str):
            selectors = [selectors]
        
        start_time = time.time()
        if not silent:
            self.logger.debug(f"⏳ Waiting for element with {len(selectors)} selectors")
        
        while time.time() - start_time < timeout:
            for selector in selectors:
                try:
                    if self.device.xpath(selector).exists:
                        if not silent:
                            self.logger.debug(f"✅ Element appeared: {selector[:50]}...")
                        self._method_stats['waits'] += 1
                        return True
                except Exception:
                    continue
            
            time.sleep(check_interval)
        
        if not silent:
            self.logger.warning(f"⏳ Element did not appear after {timeout}s")
        
        return False
    
    def _element_exists(self, selectors: Union[List[str], str], timeout: float = 2.0) -> bool:
        """Check if element exists."""
        if isinstance(selectors, str):
            selectors = [selectors]
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            for selector in selectors:
                try:
                    if self.device.xpath(selector).exists:
                        return True
                except Exception:
                    continue
            
            time.sleep(0.3)
        
        return False
    
    def _get_element_text(self, selectors: Union[List[str], str], timeout: float = 5.0) -> Optional[str]:
        """Get text from element."""
        if isinstance(selectors, str):
            selectors = [selectors]
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            for selector in selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        text = element.get_text()
                        if text:
                            return text.strip()
                except Exception as e:
                    self.logger.debug(f"Error getting text from {selector[:50]}: {e}")
                    continue
            
            time.sleep(0.5)
        
        return None
    
    def _input_text(self, selectors: Union[List[str], str], text: str, 
                   timeout: float = 5.0, clear_first: bool = True) -> bool:
        """Input text into element using Taktik Keyboard."""
        if isinstance(selectors, str):
            selectors = [selectors]
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            for selector in selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        # Click to focus first
                        element.click()
                        time.sleep(0.3)
                        
                        if clear_first:
                            # Clear using Taktik Keyboard
                            self._clear_text_with_taktik_keyboard()
                            time.sleep(0.2)
                        
                        # Use Taktik Keyboard for reliable text input
                        if not self._type_with_taktik_keyboard(text):
                            self.logger.warning("Taktik Keyboard failed, falling back to send_keys")
                            self.device.send_keys(text)
                        
                        self._human_like_delay('typing')
                        return True
                except Exception as e:
                    self.logger.debug(f"Error inputting text to {selector[:50]}: {e}")
                    continue
            
            time.sleep(0.5)
        
        self.logger.warning(f"Failed to input text after {timeout}s")
        return False
    
    def _get_device_serial(self) -> str:
        """Get the device serial/ID for ADB commands."""
        try:
            return self.device._d.serial
        except Exception:
            try:
                return self.device.device.serial
            except Exception:
                return ''
    
    def _is_taktik_keyboard_active(self) -> bool:
        """Check if Taktik Keyboard (ADB Keyboard) is the active IME."""
        try:
            device_serial = self._get_device_serial()
            result = run_adb_shell(device_serial, 'settings get secure default_input_method')
            return TAKTIK_KEYBOARD_IME in result
        except Exception as e:
            self.logger.debug(f"Cannot check keyboard status: {e}")
            return False
    
    def _activate_taktik_keyboard(self) -> bool:
        """Activate Taktik Keyboard as the default IME."""
        try:
            device_serial = self._get_device_serial()
            
            # Enable the IME
            run_adb_shell(device_serial, f'ime enable {TAKTIK_KEYBOARD_IME}')
            
            # Set as default
            result = run_adb_shell(device_serial, f'ime set {TAKTIK_KEYBOARD_IME}')
            
            if 'selected' in result.lower():
                self.logger.debug("✅ Taktik Keyboard activated")
                return True
            else:
                self.logger.warning(f"⚠️ Failed to activate Taktik Keyboard: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error activating Taktik Keyboard: {e}")
            return False
    
    def _type_with_taktik_keyboard(self, text: str, delay_mean: int = 80, delay_deviation: int = 30) -> bool:
        """
        Type text using Taktik Keyboard (ADB Keyboard) via broadcast.
        This is more reliable than uiautomator2's send_keys for special characters.
        
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
                    self.logger.warning("⚠️ Could not activate Taktik Keyboard, falling back to send_keys")
                    return False
            
            # Encode text as base64
            text_b64 = base64.b64encode(text.encode('utf-8')).decode('utf-8')
            
            # Send broadcast with text
            broadcast_cmd = f'am broadcast -a {IME_MESSAGE_B64} --es msg {text_b64} --ei delay_mean {delay_mean} --ei delay_deviation {delay_deviation}'
            result = run_adb_shell(device_serial, broadcast_cmd)
            
            if result and 'error' not in result.lower():
                # Wait for typing to complete
                typing_time = (delay_mean * len(text) + delay_deviation) / 1000
                self.logger.debug(f"⌨️ Taktik Keyboard typing '{text[:20]}...' ({typing_time:.1f}s)")
                time.sleep(typing_time + 0.5)  # Add small buffer
                return True
            else:
                self.logger.warning(f"⚠️ Taktik Keyboard broadcast failed: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error using Taktik Keyboard: {e}")
            return False
    
    def _clear_text_with_taktik_keyboard(self) -> bool:
        """Clear the current text field using Taktik Keyboard."""
        try:
            device_serial = self._get_device_serial()
            
            # Ensure Taktik Keyboard is active
            if not self._is_taktik_keyboard_active():
                self._activate_taktik_keyboard()
            
            result = run_adb_shell(device_serial, f'am broadcast -a {IME_CLEAR_TEXT}')
            time.sleep(0.3)
            return bool(result) and 'error' not in result.lower()
        except Exception as e:
            self.logger.debug(f"Error clearing text: {e}")
            return False
    
    def _scroll_up(self, scale: float = 0.8):
        """Scroll up (swipe down)."""
        self.device.swipe_down(scale)
        self._human_like_delay('scroll')
    
    def _scroll_down(self, scale: float = 0.8):
        """Scroll down (swipe up)."""
        self.device.swipe_up(scale)
        self._human_like_delay('scroll')
    
    def _swipe_to_next_video(self):
        """Swipe to next video (TikTok specific)."""
        self.device.swipe_up(scale=0.8)
        self._human_like_delay('scroll')
    
    def _swipe_to_previous_video(self):
        """Swipe to previous video (TikTok specific)."""
        self.device.swipe_down(scale=0.8)
        self._human_like_delay('scroll')
    
    def _double_tap_to_like(self):
        """Double tap center of screen to like video (TikTok specific)."""
        width, height = self.device.get_screen_size()
        x = width // 2
        y = height // 2
        
        self.device.double_click(x, y)
        self._human_like_delay('click')
    
    def _press_back(self):
        """Press back button."""
        self.device.press_back()
        self._human_like_delay('navigation')
    
    def _close_popup(self) -> bool:
        """Try to close any popup."""
        from ...ui.selectors import POPUP_SELECTORS
        
        if self._find_and_click(POPUP_SELECTORS.close_button, timeout=2):
            self.logger.debug("✅ Popup closed")
            return True
        
        if self._find_and_click(POPUP_SELECTORS.dismiss_button, timeout=2):
            self.logger.debug("✅ Popup dismissed")
            return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get action statistics."""
        return {
            'class': self.__class__.__name__,
            'stats': self._method_stats.copy()
        }
    
    def reset_stats(self):
        """Reset action statistics."""
        self._method_stats = {
            'clicks': 0,
            'waits': 0,
            'sleeps': 0,
            'errors': 0
        }
