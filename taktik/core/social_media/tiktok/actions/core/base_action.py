import time
import random
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union
from loguru import logger

from .device_facade import DeviceFacade
from .utils import ActionUtils


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
        """Input text into element."""
        if isinstance(selectors, str):
            selectors = [selectors]
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            for selector in selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        if clear_first:
                            element.clear_text()
                            time.sleep(0.2)
                        
                        element.set_text(text)
                        self._human_like_delay('typing')
                        return True
                except Exception as e:
                    self.logger.debug(f"Error inputting text to {selector[:50]}: {e}")
                    continue
            
            time.sleep(0.5)
        
        self.logger.warning(f"Failed to input text after {timeout}s")
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
