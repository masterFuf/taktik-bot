"""
Base Device Facade (Shared)

Provides common device interaction functionality shared between
Instagram and TikTok device facades. Platform-specific facades
inherit from this and override only what differs (app_id, swipe behavior, etc.).
"""

from typing import Any, Dict, Optional, List, Union, Tuple
from enum import Enum
import time
import os
from loguru import logger


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class BaseDeviceFacade:
    """Base device facade wrapping uiautomator2 device.
    
    Subclasses must set:
        - app_id: str (e.g. 'com.instagram.android')
        - _facade_name: str (e.g. 'InstagramDeviceFacade')
    """
    
    app_id: str = ''
    _facade_name: str = 'BaseDeviceFacade'
    
    def __init__(self, device, module_name: str = "shared-device-facade"):
        self.logger = logger.bind(module=module_name)
        
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
    
    # =========================================================================
    # Health & Stats
    # =========================================================================
    
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
                'wrapper_type': self._facade_name
            }
            
            if hasattr(self._device, 'get_stats'):
                stats['core_device_stats'] = self._device.get_stats()
            
            return stats
            
        except Exception as e:
            return {
                'error': str(e),
                'device_type': 'unknown'
            }
    
    # =========================================================================
    # Screen
    # =========================================================================
    
    def get_screen_size(self) -> Tuple[int, int]:
        try:
            info = self._device.info
            return info['displayWidth'], info['displayHeight']
        except Exception as e:
            self.logger.warning(f"⚠️ Cannot get screen dimensions: {e}")
            return 1080, 1920
    
    def get_xml_dump(self) -> Optional[str]:
        """Get a single XML dump of the current screen for batch operations."""
        try:
            return self._device.dump_hierarchy()
        except Exception as e:
            self.logger.error(f"Error getting XML dump: {e}")
            return None
    
    def screenshot(self, filename: str) -> bool:
        try:
            os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
            self._device.screenshot(filename)
            return True
        except Exception as e:
            self.logger.error(f"Error taking screenshot: {e}")
            return False
    
    def screenshot_pil(self):
        """Take a screenshot and return it as a PIL Image (in-memory, no file I/O)."""
        try:
            return self._device.screenshot()
        except Exception as e:
            self.logger.error(f"Error taking PIL screenshot: {e}")
            return None
    
    # =========================================================================
    # XPath & Element Finding
    # =========================================================================
    
    def xpath(self, xpath: str):
        try:
            return self._device.xpath(xpath)
        except Exception as e:
            self.logger.error(f"Error executing XPath query {xpath}: {e}")
            return None
    
    def find(self, **kwargs):
        try:
            if 'resourceId' in kwargs and self.app_id and not kwargs['resourceId'].startswith(f"{self.app_id}:"):
                kwargs['resourceId'] = f"{self.app_id}:id/{kwargs['resourceId']}"
            
            return self._device(**kwargs)
        except Exception as e:
            self.logger.error(f"Error finding element {kwargs}: {e}")
            return None
    
    # =========================================================================
    # Swipe (base implementations — can be overridden by subclasses)
    # =========================================================================
    
    def swipe_coordinates(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        try:
            self.logger.debug(f"🔧 Swipe coordinates: ({x1}, {y1}) → ({x2}, {y2}) in {duration}s")
            self._device.swipe(x1, y1, x2, y2, duration=duration)
            time.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Error swiping from ({x1}, {y1}) to ({x2}, {y2}): {e}")
            raise
    
    def swipe_up(self, scale: float = 0.8):
        """Swipe up — default implementation using swipe_ext."""
        try:
            self._device.swipe_ext("up", scale=scale)
            time.sleep(1)
        except Exception as e:
            self.logger.error(f"Error swiping up: {e}")
    
    def swipe_down(self, scale: float = 0.8):
        """Swipe down — default implementation using swipe_ext."""
        try:
            self._device.swipe_ext("down", scale=scale)
            time.sleep(1)
        except Exception as e:
            self.logger.error(f"Error swiping down: {e}")
    
    def swipe_left(self, scale: float = 0.8):
        try:
            self._device.swipe_ext("left", scale=scale)
            time.sleep(1)
        except Exception as e:
            self.logger.error(f"Error swiping left: {e}")
    
    def swipe_right(self, scale: float = 0.8):
        try:
            self._device.swipe_ext("right", scale=scale)
            time.sleep(1)
        except Exception as e:
            self.logger.error(f"Error swiping right: {e}")
    
    def swipe(self, direction: Union[Direction, str], scale: float = 0.8):
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
    
    # =========================================================================
    # Click & Press
    # =========================================================================
    
    def click_coordinates(self, x: int, y: int) -> bool:
        try:
            self.logger.debug(f"Clicking on coordinates ({x}, {y})")
            self._device.click(x, y)
            time.sleep(0.5)
            return True
        except Exception as e:
            self.logger.error(f"Error clicking on coordinates ({x}, {y}): {e}")
            return False
    
    def double_click(self, x: int, y: int):
        try:
            self._device.double_click(x, y)
            time.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Error double clicking at ({x}, {y}): {e}")
            raise
    
    def long_click(self, x: int, y: int, duration: float = 1.0):
        try:
            self._device.long_click(x, y, duration)
            time.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Error long clicking at ({x}, {y}): {e}")
            raise

    def human_tap(self, bounds, *, rng=None):
        """Tap a human-sampled point inside `bounds` (left, top, right, bottom): a point
        near the centre but never the dead centre twice and never the rim, with a varied
        finger-down time. Returns the tapped (x, y) on success, else None.

        Use this instead of clicking an element's exact centre — it removes the
        "always the same pixel" touch-heatmap fingerprint. Sampling logic lives in
        `taktik/core/shared/behavior/tap.py`.
        """
        from taktik.core.shared.behavior.tap import sample_tap_point, sample_tap_down_ms
        try:
            x, y = sample_tap_point(bounds, rng=rng)
            down_s = sample_tap_down_ms(rng=rng) / 1000.0
            self.logger.debug(f"👆 Human tap ({x}, {y}) down={down_s:.3f}s in {tuple(bounds)}")
            # A short, sub-threshold press (touch-down → wait → up) varies the contact
            # time vs an instant click, while staying a tap (never a long-press).
            self._device.long_click(x, y, down_s)
            time.sleep(0.05)
            return (x, y)
        except Exception as e:
            self.logger.error(f"Error human-tapping in {bounds}: {e}")
            return None

    def press_back(self):
        try:
            self._device.press("back")
            time.sleep(0.3)
        except Exception as e:
            self.logger.error(f"Error pressing back: {e}")
    
    def press_home(self):
        try:
            self._device.press("home")
            time.sleep(0.3)
        except Exception as e:
            self.logger.error(f"Error pressing home: {e}")
    
    def sleep(self, seconds: float):
        time.sleep(seconds)
    
    # =========================================================================
    # String representations
    # =========================================================================
    
    def __str__(self) -> str:
        return f"{self._facade_name}({type(self._device).__name__})"
    
    def __repr__(self) -> str:
        return f"{self._facade_name}(device={self._device!r})"
