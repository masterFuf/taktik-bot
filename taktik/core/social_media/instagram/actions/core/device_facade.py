from typing import Any, Dict, Optional, List, Union, Tuple
from enum import Enum
import time
import re
from lxml import etree
from loguru import logger

from taktik.core.shared.device_facade import BaseDeviceFacade, Direction


class DeviceFacade(BaseDeviceFacade):
    """Instagram-specific device facade.
    
    Inherits common functionality from BaseDeviceFacade.
    Adds Instagram-specific features: press() with key mapping,
    click() by xpath, batch_xpath_check with lxml.
    """
    
    app_id = 'com.instagram.android'
    _facade_name = 'InstagramDeviceFacade'
    
    def __init__(self, device):
        super().__init__(device, module_name="instagram-device-facade")
    
    # =========================================================================
    # Instagram-specific: press() with key mapping
    # =========================================================================
    
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
    
    def home(self):
        try:
            self._device.press("home")
            time.sleep(1)
        except Exception as e:
            self.logger.error(f"Error pressing home button: {e}")
    
    # =========================================================================
    # Instagram-specific: click() by xpath string
    # =========================================================================
    
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
    
    # =========================================================================
    # Instagram-specific: batch XML operations with lxml
    # =========================================================================
    
    def xpath_exists_in_xml(self, xml_content: str, xpath: str) -> bool:
        """Check if xpath exists in pre-fetched XML content (fast, no ADB call)."""
        try:
            tree = etree.fromstring(xml_content.encode('utf-8'))
            result = tree.xpath(xpath)
            return len(result) > 0
        except Exception:
            return False
    
    def batch_xpath_check(self, selectors_dict: Dict[str, List[str]]) -> Dict[str, bool]:
        """
        Check multiple xpath selectors in a single XML dump.
        Much faster than individual checks (1 ADB call vs N calls).
        
        Args:
            selectors_dict: Dict mapping names to list of xpath selectors
                           e.g. {'is_private': ['//*[@text="Private"]', ...], ...}
        
        Returns:
            Dict mapping names to boolean results
        """
        results = {name: False for name in selectors_dict}
        
        xml_content = self.get_xml_dump()
        if not xml_content:
            return results
        
        try:
            tree = etree.fromstring(xml_content.encode('utf-8'))
            
            for name, selectors in selectors_dict.items():
                for selector in selectors:
                    try:
                        if tree.xpath(selector):
                            results[name] = True
                            break
                    except Exception:
                        continue
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in batch xpath check: {e}")
            return results
