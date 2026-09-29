"""Navigation and recovery methods for the followers workflow."""

import time
from typing import Dict, Any


class FollowerNavigationMixin:
    """Mixin: back-to-list navigation and recovery logic."""
    
    def _go_back_to_list(self) -> bool:
        """
        Tap the Instagram back button to come back to the list.
        More reliable than the hardware back key, which can cause unwanted scrolls.
        """
        try:
            # Try the in-app back button
            clicked = False
            for selector in self._back_button_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element.click()
                        self.logger.debug("⬅️ Clicked Instagram back button")
                        self._human_like_delay('navigation')
                        clicked = True
                        break
                except Exception:
                    continue
            
            if not clicked:
                # Fallback: the system button
                self.logger.debug("⬅️ Using system back button (fallback)")
                self.device.press('back')
                self._human_like_delay('click')
            
            # Confirm we came back to the followers list
            if self.detection_actions.is_followers_list_open():
                self.logger.debug("✅ Back to followers list confirmed")
                return True
            else:
                self.logger.warning("⚠️ Back clicked but not on followers list")
                return False
            
        except Exception as e:
            self.logger.error(f"Error going back: {e}")
            self.device.press('back')
            self._human_like_delay('click')
            return False
    
    def _ensure_on_followers_list(self, target_username: str = None, force_back: bool = False) -> bool:
        """
        Make sure we are on the followers list.
        Tries several backs, then as a last resort navigates back to the target.
        
        Args:
            target_username: target username, for the last-resort recovery
            force_back: always press back first, to be used after visiting a profile
        
        True when we are on the list.
        """
        # Without a forced back, check whether we are already on the list
        if not force_back and self.detection_actions.is_followers_list_open():
            return True
        
        # Selectors UNIQUE to the followers list
        quick_check_selectors = self._followers_list_selectors.list_indicators
        
        # Helper telling whether we are on the list
        def is_on_followers_list() -> bool:
            for selector in quick_check_selectors:
                try:
                    exists = self.device.xpath(selector).exists
                    self.logger.debug(f"🔍 Checking selector: {selector[:50]}... = {exists}")
                    if exists:
                        return True
                except Exception as e:
                    self.logger.debug(f"❌ Selector error: {e}")
                    continue
            return False

        # Conditional wait: poll for the list instead of a fixed 2-2.5s sleep after a
        # back press. The list usually reappears in <1s, so this returns as soon as it's
        # there (no robotic systematic pause, no surfaced "Pause 2.5s") and only falls
        # back to the full timeout when the screen genuinely lags.
        def wait_for_followers_list(timeout: float = 2.5, interval: float = 0.25) -> bool:
            deadline = time.monotonic() + timeout
            while True:
                if is_on_followers_list():
                    return True
                if time.monotonic() >= deadline:
                    return False
                time.sleep(interval)
        
        # Selectors for the in-app back button
        back_button_selectors = self.navigation_selectors.back_buttons_action_bar
        
        # Helper tapping the in-app back button
        def click_ui_back_button() -> bool:
            for selector in back_button_selectors:
                try:
                    elem = self.device.xpath(selector)
                    if elem.exists:
                        elem.click()
                        self.logger.info(f"✅ Clicked UI back button")
                        return True
                except Exception as e:
                    self.logger.debug(f"❌ Back button error: {e}")
                    continue
            # Fallback on the hardware key when the button is not found
            self.logger.warning(f"⚠️ UI back button not found, using device.press('back')")
            self.device.press('back')
            return True
        
        # First back, coming from a profile
        self.logger.info(f"🔄 Recovery - clicking back button (1st) to return to followers list")
        click_ui_back_button()
        if wait_for_followers_list():
            self.logger.info(f"✅ Recovered to followers list (1st back)")
            return True

        # When one back was not enough we may be on the profile
        # (a post leads back to the profile, so a second back is needed)
        self.logger.info(f"🔄 First back didn't reach list, trying 2nd back...")
        click_ui_back_button()
        if wait_for_followers_list():
            self.logger.info(f"✅ Recovered to followers list (2nd back)")
            return True

        # Last nudge: give the screen more time and detect again
        self.logger.info(f"🔄 Detection failed, waiting a bit more and retrying...")
        if wait_for_followers_list(timeout=1.5):
            self.logger.info(f"✅ Recovered to followers list (after wait)")
            return True
        
        # Last resort: navigate back to the target, losing the position
        if target_username:
            self.logger.warning(f"⚠️ Could not recover via back, navigating to @{target_username}")
            if self.nav_actions.navigate_to_profile(target_username):
                self._random_sleep(0.5, 1.0)  # Short delay after navigation
                if self.nav_actions.open_followers_list():
                    self._random_sleep(0.5, 1.0)  # Short delay
                    self.logger.warning("⚠️ Recovered but position in list is lost")
                    return True
        
        self.logger.error("❌ Could not recover to followers list")
        return False
