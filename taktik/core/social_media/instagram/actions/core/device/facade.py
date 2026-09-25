from typing import Any, Dict, Optional, List, Union, Tuple
from enum import Enum
import time
import re
from loguru import logger

from taktik.core.shared.device.facade import BaseDeviceFacade, Direction
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.clone import get_active_package


class DeviceFacade(BaseDeviceFacade):
    """Instagram-specific device facade.

    Inherits common functionality from BaseDeviceFacade.
    Adds Instagram-specific features: press() that returns the device's answer,
    click() by xpath, batch_xpath_check on one dump.
    """

    @property
    def app_id(self):
        return get_active_package()
    _facade_name = 'InstagramDeviceFacade'

    # The key names the uiautomator2 server's `pressKey` knows. It answers False, without an
    # error, to any other string ("KEYCODE_BACK", "ctrl+a"), so such a key is never sent.
    SERVER_KEY_NAMES = frozenset({
        "home", "back", "left", "right", "up", "down", "center", "menu", "search", "enter",
        "delete", "del", "recent", "volume_up", "volume_down", "volume_mute", "camera", "power",
    })

    def __init__(self, device):
        super().__init__(device, module_name="instagram-device-facade")

    # =========================================================================
    # Key press
    # =========================================================================

    def press(self, key: Union[str, int]) -> bool:
        """Press a key the way the shared `press_back()` does: a key name the server knows, or
        an Android key code (int). Returns what the server answers; False for a key it cannot
        press, which is then not sent."""
        try:
            if isinstance(key, int) and not isinstance(key, bool):
                sent = key
            else:
                sent = str(key).strip().lower()
                if sent not in self.SERVER_KEY_NAMES:
                    self.logger.warning(f"Key {key!r} is not one the device can press; not sent")
                    return False
            result = self._device.press(sent)
            time.sleep(0.5)
            return bool(result)

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
            tree = parse_ui_dump(xml_content)
            result = tree.xpath(xpath) if tree is not None else []
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
            # The tree `d.xpath()` sees: a selector written by tag matches here too.
            tree = parse_ui_dump(xml_content)
            if tree is None:
                return results
            
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
