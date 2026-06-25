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

from taktik.core.shared.telemetry import emit_step


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
    # Humanized scroll — the SHARED entry point. Every workflow/action should scroll
    # through here, never a raw fixed-coordinate swipe. Reuses the single calibrated
    # gesture engine (`GestureMixin`, geometry sampled from real human trajectories)
    # via a thin adapter, so IG + TikTok + every surface share one humanization source.
    # =========================================================================

    # Page direction -> finger gesture direction: advancing the feed ("down" / reveal the NEXT
    # content) is a finger swipe UP; going back ("up") is a finger swipe DOWN.
    _PAGE_TO_GESTURE = {"down": "up", "up": "down"}

    def _gesture_host(self):
        """Lazily build (and cache) the `GestureMixin` host bound to THIS facade. Screen size is
        re-read each call so the gesture follows rotation. Cheap; avoids duplicating the engine."""
        from taktik.core.shared.behavior.gesture_primitives import GestureMixin

        host = self.__dict__.get("_gesture_host_obj")
        if host is None:
            class _FacadeGestureHost(GestureMixin):
                """Adapter: GestureMixin expects `self.device` to be the facade (so
                `self.device._device` is the raw u2 and `self.device.swipe_coordinates` exists)."""
                pass
            host = _FacadeGestureHost()
            host.device = self
            host.logger = self.logger
            self.__dict__["_gesture_host_obj"] = host
        try:
            host.screen_width, host.screen_height = self.get_screen_size()
        except Exception:
            host.screen_width, host.screen_height = 1080, 1920
        return host

    def human_scroll(self, direction: str = "down", distance_ratio: Optional[float] = None,
                     coast: bool = False) -> bool:
        """Humanized VERTICAL scroll — the single entry point for human-like feed/list/grid
        scrolling. `direction='down'` advances (reveals the NEXT content), `'up'` goes back.
        `coast=True` fires a real Android fling (`_strong_flick`, content coasts ~2.5-4x — a natural
        feed advance); `coast=False` (default) is a 1:1 controlled curve (`_human_swipe`) that
        preserves a precise travel distance (safe drop-in for detection/extraction loops, no
        overshoot). `distance_ratio` = gesture magnitude as a fraction of screen height."""
        host = self._gesture_host()
        g_dir = self._PAGE_TO_GESTURE.get(direction, "up")
        distance_px = (distance_ratio * host.screen_height) if distance_ratio else None
        if coast:
            return host._strong_flick(direction=g_dir, distance_px=distance_px)
        return host._human_swipe(direction=g_dir, distance_px=distance_px)

    def human_hswipe(self, direction: str = "left", distance_ratio: float = 0.6,
                     y_ratio: Optional[float] = None) -> bool:
        """Humanized HORIZONTAL swipe (stories, carousels, story/highlight trays). `direction='left'`
        reveals the NEXT slide, `'right'` the previous. Dedicated horizontal profile (varied start
        point, vertical wobble, varied duration) — never a fixed-coordinate robotic swipe. `y_ratio`
        pins the swipe row (e.g. a top story tray ~0.17h); default samples the mid band."""
        return self._gesture_host()._human_horizontal_swipe(direction, distance_ratio, y_ratio=y_ratio)

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

    def human_tap(self, bounds, *, rng=None, quick=False):
        """Tap a human-sampled point inside `bounds` (left, top, right, bottom): a point
        near the centre but never the dead centre twice and never the rim, with a varied
        finger-down time. Returns the tapped (x, y) on success, else None.

        Use this instead of clicking an element's exact centre — it removes the
        "always the same pixel" touch-heatmap fingerprint. Sampling logic lives in
        `taktik/core/shared/behavior/tap.py`. Set `quick=True` for surfaces where a held
        press has a meaning (e.g. a story pauses on touch-and-hold) → instant tap.
        """
        from taktik.core.shared.behavior.tap import sample_tap_point, sample_tap_down_ms
        try:
            x, y = sample_tap_point(bounds, rng=rng)
            if quick:
                self.logger.debug(f"👆 Human tap ({x}, {y}) [quick] in {tuple(bounds)}")
                self._device.click(x, y)
            else:
                down_s = sample_tap_down_ms(rng=rng) / 1000.0
                self.logger.debug(f"👆 Human tap ({x}, {y}) down={down_s:.3f}s in {tuple(bounds)}")
                # A short, sub-threshold press (touch-down → wait → up) varies the contact
                # time vs an instant click, while staying a tap (never a long-press).
                self._device.long_click(x, y, down_s)
            emit_step(
                "tap", action="quick" if quick else "press",
                x=x, y=y, bounds=list(bounds) if bounds is not None else None,
                down_ms=None if quick else round(down_s * 1000),
            )
            time.sleep(0.05)
            return (x, y)
        except Exception as e:
            self.logger.error(f"Error human-tapping in {bounds}: {e}")
            return None

    def human_double_tap(self, bounds, *, rng=None):
        """Double-tap a human-sampled point inside `bounds` (e.g. the post image area to
        like) — a varied point, never the fixed centre. Returns the (x, y) or None."""
        from taktik.core.shared.behavior.tap import sample_tap_point
        try:
            x, y = sample_tap_point(bounds, rng=rng)
            self.logger.debug(f"👆👆 Human double-tap ({x}, {y}) in {tuple(bounds)}")
            self._device.double_click(x, y)
            emit_step("double_tap", x=x, y=y, bounds=list(bounds) if bounds is not None else None)
            time.sleep(0.1)
            return (x, y)
        except Exception as e:
            self.logger.error(f"Error human double-tapping in {bounds}: {e}")
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
