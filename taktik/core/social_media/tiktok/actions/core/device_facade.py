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
    """Device facade for TikTok automation - wraps uiautomator2 device."""
    
    def __init__(self, device):
        self.logger = logger.bind(module="tiktok-device-facade")
        self.app_id = 'com.zhiliaoapp.musically'  # TikTok package name
        
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
        """Delegate attribute access to underlying device."""
        return getattr(self._device, name)
    
    @property
    def device(self):
        """Get underlying device object."""
        return self._device
    
    def verify_device_health(self) -> Dict[str, Any]:
        """Verify device health and connectivity."""
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
        """Ensure device is ready for interactions."""
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
        """Get device statistics."""
        try:
            stats = {
                'device_type': type(self._device).__name__,
                'health_check': self.verify_device_health(),
                'wrapper_type': 'TikTokDeviceFacade'
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
        return f"TikTokDeviceFacade({type(self._device).__name__})"
    
    def swipe_coordinates(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        """Swipe from (x1, y1) to (x2, y2)."""
        try:
            self.logger.debug(f"🔧 Swipe coordinates: ({x1}, {y1}) → ({x2}, {y2}) in {duration}s")
            self._device.swipe(x1, y1, x2, y2, duration=duration)
            time.sleep(0.1)
            
        except Exception as e:
            self.logger.error(f"Error swiping from ({x1}, {y1}) to ({x2}, {y2}): {e}")
            raise
    
    def get_screen_size(self):
        """Get screen dimensions."""
        try:
            info = self._device.info
            return info['displayWidth'], info['displayHeight']
        except Exception as e:
            self.logger.warning(f"⚠️ Cannot get screen dimensions: {e}")
            return 1080, 1920

    def __repr__(self) -> str:
        return f"TikTokDeviceFacade(device={self._device!r})"
    
    def xpath(self, xpath: str):
        """Execute XPath query."""
        try:
            return self._device.xpath(xpath)
        except Exception as e:
            self.logger.error(f"Error executing XPath query {xpath}: {e}")
            return None
    
    def find(self, **kwargs):
        """Find element with resource ID handling."""
        try:
            if 'resourceId' in kwargs and not kwargs['resourceId'].startswith(f"{self.app_id}:"):
                kwargs['resourceId'] = f"{self.app_id}:id/{kwargs['resourceId']}"
            
            return self._device(**kwargs)
        except Exception as e:
            self.logger.error(f"Error finding element with {kwargs}: {e}")
            return None
    
    def swipe_up(self, scale: float = 0.8):
        """Swipe up (scroll down content).
        
        Adaptive swipe for TikTok video scrolling that works on all screen resolutions:
        - Uses percentage-based coordinates to adapt to any screen size
        - Swipes on LEFT side of screen to avoid interaction buttons on the right
        - Avoids bottom ~20% (navigation bar + interaction buttons area)
        - Avoids top ~15% (search bar/status bar area)
        - Results in ~65% screen distance swipe for reliable video switching
        """
        width, height = self.get_screen_size()
        
        # Use LEFT side of screen (30% from left) to avoid interaction buttons on right
        # Interaction buttons (like, comment, share) are on the right side (x > 80%)
        x = int(width * 0.30)
        
        # Percentage-based swipe that adapts to any resolution
        # Start at 80% from top (avoids bottom nav + buttons area ~20%)
        # End at 15% from top (avoids search bar + header)
        y_start = int(height * 0.80)
        y_end = int(height * 0.15)
        
        self.logger.debug(f"Swipe up: screen={width}x{height}, y={y_start}->{y_end}")
        self.swipe_coordinates(x, y_start, x, y_end, duration=0.35)
    
    def swipe_down(self, scale: float = 0.8):
        """Swipe down (scroll up content)."""
        width, height = self.get_screen_size()
        x = width // 2
        y_start = int(height * 0.2)
        y_end = int(height * 0.8)
        
        self.swipe_coordinates(x, y_start, x, y_end, duration=0.3)
    
    def swipe_left(self, scale: float = 0.8):
        """Swipe left."""
        width, height = self.get_screen_size()
        y = height // 2
        x_start = int(width * 0.8)
        x_end = int(width * 0.2)
        
        self.swipe_coordinates(x_start, y, x_end, y, duration=0.3)
    
    def swipe_right(self, scale: float = 0.8):
        """Swipe right."""
        width, height = self.get_screen_size()
        y = height // 2
        x_start = int(width * 0.2)
        x_end = int(width * 0.8)
        
        self.swipe_coordinates(x_start, y, x_end, y, duration=0.3)
    
    def swipe(self, direction: Union[Direction, str], scale: float = 0.8):
        """Swipe in specified direction."""
        if isinstance(direction, str):
            direction = Direction(direction.lower())
        
        swipe_methods = {
            Direction.UP: self.swipe_up,
            Direction.DOWN: self.swipe_down,
            Direction.LEFT: self.swipe_left,
            Direction.RIGHT: self.swipe_right
        }
        
        swipe_method = swipe_methods.get(direction)
        if swipe_method:
            swipe_method(scale)
        else:
            self.logger.error(f"Unknown swipe direction: {direction}")
    
    def click(self, x: int, y: int):
        """Click at coordinates."""
        try:
            self._device.click(x, y)
            time.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Error clicking at ({x}, {y}): {e}")
            raise
    
    def long_click(self, x: int, y: int, duration: float = 1.0):
        """Long click at coordinates."""
        try:
            self._device.long_click(x, y, duration)
            time.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Error long clicking at ({x}, {y}): {e}")
            raise
    
    def double_click(self, x: int, y: int):
        """Double click at coordinates (for liking videos)."""
        try:
            self._device.double_click(x, y)
            time.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Error double clicking at ({x}, {y}): {e}")
            raise
    
    def press_back(self):
        """Press back button."""
        try:
            self._device.press("back")
            time.sleep(0.3)
        except Exception as e:
            self.logger.error(f"Error pressing back: {e}")
            raise
    
    def press_home(self):
        """Press home button."""
        try:
            self._device.press("home")
            time.sleep(0.3)
        except Exception as e:
            self.logger.error(f"Error pressing home: {e}")
            raise
