import time
import random
from typing import Optional, Dict, Any, List, Union
from loguru import logger

from .device_facade import DeviceFacade
from .utils import ActionUtils

from taktik.core.shared.actions.base_action import SharedBaseAction

# Re-export for backward compatibility (some files import these from here)
TAKTIK_KEYBOARD_PKG = 'com.alexal1.adbkeyboard'


class BaseAction(SharedBaseAction):
    """Base class for all TikTok actions.
    
    Inherits shared functionality (element finding, clicking, waiting,
    Taktik Keyboard, delays) from SharedBaseAction.
    
    Adds TikTok-specific:
    - video_watch delay type
    - _element_exists with timeout (polling variant)
    - _get_element_text with timeout (polling variant)
    - _input_text (click + clear + type)
    - _scroll_up / _scroll_down
    - _swipe_to_next_video / _swipe_to_previous_video
    - _double_tap_to_like
    - _close_popup
    """
    
    _device_facade_class = DeviceFacade
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module=f"tiktok.actions.{self.__class__.__name__.lower()}")
        self.utils = ActionUtils()
    
    def _human_like_delay(self, action_type: str = 'general') -> None:
        """Add human-like delay based on action type (with TikTok video_watch)."""
        delays = {
            'click': (0.2, 0.5),      
            'navigation': (0.7, 1.5),  
            'scroll': (0.3, 0.7),      
            'typing': (0.08, 0.15),    
            'video_watch': (2.0, 5.0),
            'default': (0.3, 0.8)      
        }
        
        min_delay, max_delay = delays.get(action_type, delays['default'])
        self._random_sleep(min_delay, max_delay)
    
    # =========================================================================
    # TikTok-specific: element methods with polling timeout
    # =========================================================================
    
    def _element_exists(self, selectors: Union[List[str], str], timeout: float = 2.0) -> bool:
        """Check if element exists (with polling timeout)."""
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
        """Get text from element (with polling timeout)."""
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
    
    # =========================================================================
    # TikTok-specific: scroll & video navigation
    # =========================================================================
    
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
