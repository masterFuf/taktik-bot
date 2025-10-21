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
    def __init__(self, device):
        self.device = device if isinstance(device, DeviceFacade) else DeviceFacade(device)
        self.logger = logger.bind(module=f"instagram.actions.{self.__class__.__name__.lower()}")
        self.utils = ActionUtils()
        
        self._method_stats = {
            'clicks': 0,
            'waits': 0,
            'sleeps': 0,
            'errors': 0
        }
        
    def _random_sleep(self, min_delay: float = 0.3, max_delay: float = 0.8) -> None:
        delay = random.uniform(min_delay, max_delay)
        self.logger.debug(f"⏱️ Random sleep: {delay:.2f}s")
        time.sleep(delay)
    
    def _human_like_delay(self, action_type: str = 'general') -> None:
        delays = {
            'click': (0.2, 0.5),      
            'navigation': (0.7, 1.5),  
            'scroll': (0.3, 0.7),      
            'typing': (0.08, 0.15),    
            'default': (0.3, 0.8)      
        }
        
        min_delay, max_delay = delays.get(action_type, delays['default'])
        self._random_sleep(min_delay, max_delay)
    
    def _find_and_click(self, selectors: Union[List[str], str], timeout: float = 5.0, 
                       human_delay: bool = True) -> bool:
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

    def _scroll_down(self, distance: int = 500) -> None:
        screen_size = self.device.info['displayHeight']
        start_y = int(screen_size * 0.7)
        end_y = int(screen_size * 0.3)
        
        self.device.swipe(540, start_y, 540, end_y)
        self._human_like_delay('scroll')
    
    def _scroll_up(self, distance: int = 500) -> None:
        screen_size = self.device.info['displayHeight']
        start_y = int(screen_size * 0.3)
        end_y = int(screen_size * 0.7)
        
        self.device.swipe(540, start_y, 540, end_y)
        self._human_like_delay('scroll')
    
    def _press_back(self, count: int = 1) -> None:
        for _ in range(count):
            self.device.press('back')
            self._human_like_delay('click')
    
    def _is_instagram_open(self) -> bool:
        try:
            current_app = self.device.app_current()
            return current_app.get('package') == 'com.instagram.android'
        except Exception:
            return False
    
    def _open_instagram(self) -> bool:
        try:
            self.device.app_start('com.instagram.android')
            self._human_like_delay('navigation')
            return self._is_instagram_open()
        except Exception as e:
            self.logger.error(f"Error opening Instagram: {e}")
            return False
    
    def _debug_current_screen(self, description: str = "") -> None:
        try:
            current_app = self.device.app_current()
            activity = current_app.get('activity', 'Unknown')
            
            self.logger.debug(f"🔍 Debug screen {description}")
            self.logger.debug(f"📱 Activity: {activity}")
            self.logger.debug(f"📊 Stats: {self._method_stats}")
        except Exception as e:
            self.logger.debug(f"Debug error: {e}")
    
    def get_method_stats(self) -> Dict[str, int]:
        return self._method_stats.copy()
    
    def reset_stats(self) -> None:
        self._method_stats = {key: 0 for key in self._method_stats}
        self.logger.debug("📊 Stats reset")
        
    def _extract_number_from_text(self, text: str) -> Optional[int]:
        return self.utils.parse_number_from_text(text)
    
    def _clean_username(self, username: str) -> str:
        return self.utils.clean_username(username)
    
    def _is_valid_username(self, username: str) -> bool:
        return self.utils.is_valid_username(username)
