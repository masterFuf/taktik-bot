from typing import Any, Dict, Optional, List, Union, Tuple
from enum import Enum
import time
import re
from loguru import logger


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class DeviceFacade:
    def __init__(self, device):
        self.logger = logger.bind(module="instagram-device-facade")
        self.app_id = 'com.instagram.android'
        
        if device is None:
            raise ValueError("Device cannot be None - device must be properly initialized")
        
        if hasattr(device, 'device') and device.device is not None:
            self._device = device.device
            self.logger.debug("✅ Device extracted from DeviceManager")
        else:
            self._device = device
        
        if self._device is None:
            raise ValueError("Failed to properly initialize device - device propagation failed")
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._device, name)
    
    @property
    def device(self):
        return self._device
    
    def verify_device_health(self) -> Dict[str, Any]:
        try:
            health_info = {
                'device_available': True,
                'device_type': type(self._device).__name__,
                'device_info_accessible': False,
                'screen_dimensions': None,
                'current_app': None,
                'errors': []
            }
            
            try:
                device_info = self._device.info
                health_info['device_info_accessible'] = True
                health_info['screen_dimensions'] = {
                    'width': device_info.get('displayWidth', 0),
                    'height': device_info.get('displayHeight', 0)
                }
            except Exception as e:
                health_info['errors'].append(f"Device info access failed: {e}")
            
            try:
                current_app = self._device.app_current()
                health_info['current_app'] = current_app.get('package', 'unknown')
            except Exception as e:
                health_info['errors'].append(f"Current app access failed: {e}")
            
            return health_info
            
        except Exception as e:
            return {
                'device_available': False,
                'error': str(e),
                'device_type': 'unknown'
            }
    
    def ensure_device_ready(self) -> bool:
        try:
            health = self.verify_device_health()
            
            if not health['device_available']:
                self.logger.error("❌ Device not available")
                return False
            
            if not health['device_info_accessible']:
                self.logger.warning("⚠️ Device info not accessible")
                return False
            
            if health['errors']:
                self.logger.warning(f"⚠️ Device errors detected: {health['errors']}")
            
            self.logger.debug("✅ Device ready for interactions")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error verifying device: {e}")
            return False
    
    def get_device_stats(self) -> Dict[str, Any]:
        try:
            stats = {
                'device_type': type(self._device).__name__,
                'health_check': self.verify_device_health(),
                'wrapper_type': 'InstagramDeviceFacade'
            }
            
            if hasattr(self._device, 'get_stats'):
                stats['core_device_stats'] = self._device.get_stats()
            
            return stats
            
        except Exception as e:
            return {
                'error': str(e),
                'device_type': 'unknown'
            }
    
    def __str__(self) -> str:
        return f"InstagramDeviceFacade({type(self._device).__name__})"
    
    def swipe_coordinates(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        try:
            self.logger.debug(f"🔧 Swipe coordinates: ({x1}, {y1}) → ({x2}, {y2}) in {duration}s")
            self._device.swipe(x1, y1, x2, y2, duration=duration)
            time.sleep(0.1)
            
        except Exception as e:
            self.logger.error(f"Error swiping from ({x1}, {y1}) to ({x2}, {y2}): {e}")
            raise
    
    def get_screen_size(self):
        try:
            info = self._device.info
            return info['displayWidth'], info['displayHeight']
        except Exception as e:
            self.logger.warning(f"⚠️ Cannot get screen dimensions: {e}")
            return 1080, 1920

    def __repr__(self) -> str:
        return f"InstagramDeviceFacade(device={self._device!r})"
    
    def xpath(self, xpath: str):
        try:
            return self._device.xpath(xpath)
        except Exception as e:
            self.logger.error(f"Error executing XPath query {xpath}: {e}")
            return None
    
    def find(self, **kwargs):
        try:
            if 'resourceId' in kwargs and not kwargs['resourceId'].startswith(f"{self.app_id}:"):
                kwargs['resourceId'] = f"{self.app_id}:id/{kwargs['resourceId']}"
            
            return self._device(**kwargs)
        except Exception as e:
            self.logger.error(f"Error finding element {kwargs}: {e}")
            return None
    
    def swipe(self, direction: Direction, scale: float = 0.8):
        try:
            if direction == Direction.UP:
                self._device.swipe_ext("up", scale=scale)
            elif direction == Direction.DOWN:
                self._device.swipe_ext("down", scale=scale)
            elif direction == Direction.LEFT:
                self._device.swipe_ext("left", scale=scale)
            elif direction == Direction.RIGHT:
                self._device.swipe_ext("right", scale=scale)
            time.sleep(1)
        except Exception as e:
            self.logger.error(f"Error swiping {direction}: {e}")
    
    def swipe_up(self, scale: float = 0.8):
        self.swipe(Direction.UP, scale)
    
    def swipe_down(self, scale: float = 0.8):
        self.swipe(Direction.DOWN, scale)
    
    def swipe_left(self, scale: float = 0.8):
        self.swipe(Direction.LEFT, scale)
    
    def swipe_right(self, scale: float = 0.8):
        self.swipe(Direction.RIGHT, scale)
    
    def back(self):
        try:
            self._device.press("back")
            time.sleep(0.5)
        except Exception as e:
            self.logger.error(f"Error pressing back button: {e}")
    
    def home(self):
        try:
            self._device.press("home")
            time.sleep(1)
        except Exception as e:
            self.logger.error(f"Error pressing home button: {e}")
    
    def sleep(self, seconds: float):
        time.sleep(seconds)
    
    def click(self, xpath: str, timeout: float = 10.0) -> bool:
        try:
            element = self.xpath(xpath)
            if element and hasattr(element, 'click'):
                element.click(timeout=timeout)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error clicking on {xpath}: {e}")
            return False
    
    def screenshot(self, filename: str) -> bool:
        try:
            import os
            os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
            
            self._device.screenshot(filename)
            return True
            
        except Exception as e:
            self.logger.error(f"Error taking screenshot: {e}")
            return False
    
    def press(self, key: str) -> bool:
        try:
            key_mapping = {
                'profile': 'KEYCODE_APP_SWITCH',
                'activity': 'KEYCODE_NOTIFICATIONS',
                'reels': 'KEYCODE_MEDIA_PLAY_PAUSE',
                'search': 'KEYCODE_SEARCH',
                'home': 'KEYCODE_HOME',
                'back': 'KEYCODE_BACK',
                'menu': 'KEYCODE_MENU',
                'recent': 'KEYCODE_APP_SWITCH',
            }
            
            keycode = key_mapping.get(key.lower(), key)
            
            if not keycode.startswith('KEYCODE_'):
                keycode = f'KEYCODE_{keycode.upper()}'
                
            self._device.press(keycode)
            time.sleep(0.5)
            return True
            
        except Exception as e:
            self.logger.error(f"Error pressing key {key}: {e}")
            return False
    
    def back(self):
        return self.press("back")
    
    def click_coordinates(self, x: int, y: int) -> bool:
        try:
            self.logger.debug(f"Clicking on coordinates ({x}, {y})")
            self._device.click(x, y)
            time.sleep(0.5)
            return True
        except Exception as e:
            self.logger.error(f"Error clicking on coordinates ({x}, {y}): {e}")
            return False
