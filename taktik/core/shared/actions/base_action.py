"""
Shared Base Action (Shared)

Common action functionality shared between Instagram and TikTok base actions.
Handles element finding, clicking, waiting, text input via Taktik Keyboard, etc.

Platform-specific base actions inherit from this and add their own logic
(e.g. HumanBehavior for Instagram, video swipe for TikTok).
"""

import time
import random
import base64
from typing import Optional, Dict, Any, List, Union
from loguru import logger

from taktik.core.shared.device.facade import BaseDeviceFacade
from taktik.core.shared.utils.action_utils import ActionUtils
from taktik.core.shared.input.taktik_keyboard import (
    run_adb_shell,
    TAKTIK_KEYBOARD_IME,
    IME_MESSAGE_B64,
    IME_CLEAR_TEXT,
    is_taktik_keyboard_active,
    activate_taktik_keyboard,
)


class SharedBaseAction:
    """Base class for all social media actions with common functionality.
    
    Subclasses should:
    - Call super().__init__(device) with a BaseDeviceFacade (or raw device)
    - Set self.logger with appropriate module binding
    - Override _human_like_delay() if needed for platform-specific behavior
    """
    
    # Subclasses can set this to their DeviceFacade subclass
    _device_facade_class = BaseDeviceFacade
    
    def __init__(self, device):
        if isinstance(device, BaseDeviceFacade):
            self.device = device
        else:
            self.device = self._device_facade_class(device)
        
        self.logger = logger.bind(module=f"shared.actions.{self.__class__.__name__.lower()}")
        self.utils = ActionUtils()
        
        self._method_stats = {
            'clicks': 0,
            'waits': 0,
            'sleeps': 0,
            'errors': 0
        }
    
    # =========================================================================
    # Delays
    # =========================================================================
    
    def _random_sleep(self, min_delay: float = 0.3, max_delay: float = 0.8) -> None:
        """Sleep for a random duration."""
        delay = random.uniform(min_delay, max_delay)
        self.logger.debug(f"⏱️ Random sleep: {delay:.2f}s")
        time.sleep(delay)
    
    def _human_like_delay(self, action_type: str = 'general') -> None:
        """Add human-like delay based on action type.
        Override in subclass for platform-specific delays."""
        delays = {
            'click': (0.2, 0.5),
            'navigation': (0.7, 1.5),
            'scroll': (0.3, 0.7),
            'typing': (0.08, 0.15),
            'default': (0.3, 0.8)
        }
        
        min_delay, max_delay = delays.get(action_type, delays['default'])
        self._random_sleep(min_delay, max_delay)
    
    # =========================================================================
    # Element Interaction
    # =========================================================================
    
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
            self.logger.warning(f"⏰ Timeout: element not found after {timeout}s")
        self._method_stats['errors'] += 1
        return False
    
    def _is_element_present(self, selectors: Union[List[str], str]) -> bool:
        """Check if element exists (instant check, no waiting)."""
        if isinstance(selectors, str):
            selectors = [selectors]
        
        for selector in selectors:
            try:
                if self.device.xpath(selector).exists:
                    return True
            except Exception:
                continue
        
        return False
    
    def _get_text_from_element(self, selectors: Union[List[str], str]) -> Optional[str]:
        """Get text from first matching element."""
        if isinstance(selectors, str):
            selectors = [selectors]
        
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    text = element.get_text()
                    if text:
                        return text.strip()
            except Exception as e:
                self.logger.debug(f"Error getting text: {e}")
                continue
        
        return None
    
    def _get_element_attribute(self, selectors: Union[List[str], str],
                             attribute: str) -> Optional[str]:
        """Get attribute value from first matching element."""
        if isinstance(selectors, str):
            selectors = [selectors]
        
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    return element.attrib.get(attribute)
            except Exception:
                continue
        
        return None
    
    # =========================================================================
    # Navigation
    # =========================================================================
    
    def _press_back(self, count: int = 1) -> None:
        for _ in range(count):
            self.device.press_back()
            self._human_like_delay('click')
    
    # =========================================================================
    # Taktik Keyboard
    # =========================================================================
    
    def _get_device_serial(self) -> str:
        """Get the device serial for ADB commands."""
        try:
            # Try uiautomator2 serial
            if hasattr(self.device, '_d') and hasattr(self.device._d, 'serial'):
                return self.device._d.serial
        except Exception:
            pass
        
        try:
            device_serial = getattr(self.device.device, 'serial', None)
            if device_serial:
                return device_serial
        except Exception:
            pass
        
        try:
            device_info = getattr(self.device.device, '_device_info', {})
            device_serial = device_info.get('serial', '')
            if device_serial:
                return device_serial
        except Exception:
            pass
        
        self.logger.warning("⚠️ Device serial not found, using emulator-5554")
        return "emulator-5554"
    
    def _is_taktik_keyboard_active(self) -> bool:
        """Check if Taktik Keyboard (ADB Keyboard) is the active IME."""
        try:
            device_serial = self._get_device_serial()
            return is_taktik_keyboard_active(device_serial)
        except Exception as e:
            self.logger.debug(f"Cannot check keyboard status: {e}")
            return False
    
    def _activate_taktik_keyboard(self) -> bool:
        """Activate Taktik Keyboard as the default IME."""
        try:
            device_serial = self._get_device_serial()
            return activate_taktik_keyboard(device_serial)
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
    
    # =========================================================================
    # Stats
    # =========================================================================
    
    def get_method_stats(self) -> Dict[str, int]:
        return self._method_stats.copy()
    
    def reset_stats(self) -> None:
        self._method_stats = {key: 0 for key in self._method_stats}
        self.logger.debug("📊 Stats reset")
    
    # =========================================================================
    # Utility shortcuts
    # =========================================================================
    
    def _extract_number_from_text(self, text: str) -> Optional[int]:
        return self.utils.parse_number_from_text(text)
    
    def _clean_username(self, username: str) -> str:
        return self.utils.clean_username(username)
    
    def _is_valid_username(self, username: str) -> bool:
        return self.utils.is_valid_username(username)
