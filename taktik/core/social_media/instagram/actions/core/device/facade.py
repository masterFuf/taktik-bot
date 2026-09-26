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
    Adds Instagram-specific features: press() that returns the device's answer,
    click() by xpath, batch_xpath_check on one screen photo.
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

    _KEYCODE_BACK = 4

    def press(self, key: Union[str, int]) -> bool:
        """Press a key the way the shared `press_back()` does: a key name the server knows, or
        an Android key code (int). Returns what the server answers; False for a key it cannot
        press, which is then not sent. A Back on an Instagram root screen is refused."""
        try:
            if isinstance(key, int) and not isinstance(key, bool):
                sent = key
            else:
                sent = str(key).strip().lower()
                if sent not in self.SERVER_KEY_NAMES:
                    self.logger.warning(f"Key {key!r} is not one the device can press; not sent")
                    return False
            if sent in ("back", self._KEYCODE_BACK) and self._refuse_back_on_root():
                return False
            result = self._device.press(sent)
            time.sleep(0.5)
            return bool(result)

        except Exception as e:
            self.logger.error(f"Error pressing key {key}: {e}")
            return False

    def back(self):
        return self.press("back")

    def press_back(self):
        if self._refuse_back_on_root():
            return
        super().press_back()

    def is_on_root_screen(self) -> bool:
        """A main tab's own screen with nothing a Back would close: there Back leaves Instagram
        (home feed) or jumps to another tab. False when the screen cannot be read."""
        from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS

        try:
            photo = self.snapshot()
            return (photo.exists(NAVIGATION_SELECTORS.main_tab_bar)
                    and not photo.exists(NAVIGATION_SELECTORS.back_buttons)
                    and not photo.exists(NAVIGATION_SELECTORS.back_closable_layers))
        except Exception as e:
            self.logger.debug(f"Root screen check skipped, screen unreadable: {e}")
            return False

    def _refuse_back_on_root(self) -> bool:
        if not self.is_on_root_screen():
            return False
        self.logger.warning("Back refused: Instagram root screen, it would leave Instagram or switch tab")
        return True
    
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
