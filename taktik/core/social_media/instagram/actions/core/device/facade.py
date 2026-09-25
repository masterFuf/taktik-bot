from typing import Any, Dict, Optional, List, Union, Tuple
from enum import Enum
import time
import re
from loguru import logger

from taktik.core.shared.device.facade import BaseDeviceFacade, Direction
from taktik.core.shared.device.snapshot import SnapshotUnavailable
from taktik.core.clone import get_active_package


class DeviceFacade(BaseDeviceFacade):
    """Instagram-specific device facade.
    
    Inherits common functionality from BaseDeviceFacade.
    Adds Instagram-specific features: press() with key mapping,
    click() by xpath, batch_xpath_check on one screen photo.
    """
    
    @property
    def app_id(self):
        return get_active_package()
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
    # Instagram-specific: several selectors asked of one screen photo
    # =========================================================================

    def xpath_exists_in_xml(self, xml_content: str, xpath: str) -> bool:
        """Does `xpath` find anything on a dump already held? Answered on a photo of that dump,
        as `self.xpath(xpath).exists` answers on the screen: the device's rewrite (bare and
        clone ids) and uiautomator2's shorthands included. No device call."""
        try:
            return bool(self.snapshot_of(xml_content).elements(xpath))
        except Exception:
            return False

    def batch_xpath_check(self, selectors_dict: Dict[str, List[str]]) -> Dict[str, bool]:
        """Named selector lists asked of ONE photo of the screen (one dump for all of them).

        A name is True when one of its selectors finds anything, exactly as
        `self.xpath(selector).exists` would on that screen: through the device's rewrite (every
        Instagram bridge mounts `CloneAwareDeviceProxy`, which makes an id equality match a
        clone's prefix and the bare ids of the Compose screens) and uiautomator2's own
        evaluation. A selector the engine rejects is skipped; an unreadable screen answers False
        for every name.

        Args:
            selectors_dict: Dict mapping names to list of xpath selectors
                           e.g. {'is_private': ['//*[@text="Private"]', ...], ...}

        Returns:
            Dict mapping names to boolean results
        """
        results = {name: False for name in selectors_dict}
        try:
            photo = self.snapshot()
        except SnapshotUnavailable:
            return results

        for name, selectors in selectors_dict.items():
            for selector in selectors:
                try:
                    if photo.elements(selector):
                        results[name] = True
                        break
                except Exception:
                    continue
        return results
