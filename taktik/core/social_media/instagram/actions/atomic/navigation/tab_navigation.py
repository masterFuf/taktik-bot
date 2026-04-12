"""Tab-based UI navigation (home, search, profile tab)."""

import time
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import DETECTION_SELECTORS, NAVIGATION_SELECTORS, PROFILE_SELECTORS


class TabNavigationMixin(BaseAction):
    """Mixin: navigate between Instagram tabs via bottom bar clicks."""

    def _navigate_to_tab(self, tab_selectors, tab_name: str, emoji: str, verify_func) -> bool:
        """
        Generic method to navigate to a tab.
        
        Args:
            tab_selectors: Selectors for the tab
            tab_name: Name for logging
            emoji: Emoji for logging
            verify_func: Function to verify navigation success
            
        Returns:
            True if navigation successful, False otherwise
        """
        self.logger.debug(f"{emoji} Navigating to {tab_name}")
        
        if self._find_and_click(tab_selectors, timeout=3):
            self._human_like_delay('navigation')
            return verify_func()
        
        return False
    
    def navigate_to_home(self) -> bool:
        if self._navigate_to_tab(self.selectors.home_tab, "home screen", "🏠", self._is_home_screen):
            return True
        
        self.logger.debug("Fallback: using back button")
        self._press_back(3)
        return self._is_home_screen()
    
    def navigate_to_search(self) -> bool:
        return self._navigate_to_tab(self.selectors.search_tab, "search screen", "🔍", self._is_search_screen)
    
    def navigate_to_profile_tab(self) -> bool:
        self.logger.debug("👤 Navigating to profile tab")
        
        max_attempts = 3
        
        for attempt in range(max_attempts):
            from ..detection import DetectionActions
            detection = DetectionActions(self.device)
            
            if detection.is_on_own_profile():
                self.logger.debug("✅ Already on own profile")
                return True
            
            # If on someone else's profile, press back to pop navigation stack
            # (Instagram restores nav state after restart, clicking profile_tab
            # when already on the profile tab doesn't navigate back)
            if detection.is_on_profile_screen():
                self.logger.debug(f"📱 On another user's profile, pressing back (attempt {attempt + 1})")
                self._press_back(1)
                self._human_like_delay('navigation')
                if detection.is_on_own_profile():
                    self.logger.debug(f"✅ Back to own profile via back button (attempt {attempt + 1})")
                    return True
            
            if self._find_and_click(self.selectors.profile_tab, timeout=15):
                self._human_like_delay('navigation')
                
                if detection.is_on_own_profile():
                    self.logger.debug(f"✅ Successfully navigated to own profile (attempt {attempt + 1})")
                    return True
                else:
                    self.logger.debug(f"❌ Failed navigation attempt {attempt + 1}")
            else:
                self.logger.debug(f"❌ Cannot click on profile tab (attempt {attempt + 1})")
        
        self.logger.error("❌ Failed to navigate to own profile after 3 attempts")
        # Debug: dump UI hierarchy to understand what's on screen
        try:
            xml = self.device.dump_hierarchy()
            if xml:
                # Extract text/content-desc attributes for a readable snapshot
                import re
                texts = re.findall(r'text="([^"]+)"', xml)
                descs = re.findall(r'content-desc="([^"]+)"', xml)
                visible_texts = [t for t in texts if t.strip()][:20]
                visible_descs = [d for d in descs if d.strip()][:10]
                self.logger.warning(f"UI texts on screen: {visible_texts}")
                self.logger.warning(f"UI content-descs: {visible_descs}")
        except Exception as e:
            self.logger.debug(f"UI dump failed: {e}")
        return False

    # === Screen detection helpers ===

    def _is_screen(self, indicators, screen_name: str = None) -> bool:
        """Generic method to check if on a specific screen."""
        return self._is_element_present(indicators)
    
    def _is_home_screen(self) -> bool:
        return self._is_screen(self.detection_selectors.home_screen_indicators)
    
    def _is_search_screen(self) -> bool:
        return self._is_screen(self.detection_selectors.search_screen_indicators)
    
    def _is_profile_screen(self) -> bool:
        return self._is_screen(self.detection_selectors.profile_screen_indicators)
    
    def _is_followers_list_open(self) -> bool:
        return self._is_screen(self.detection_selectors.followers_list_indicators)
    
    def _is_following_list_open(self) -> bool:
        return self._is_followers_list_open()

    # === Popup/modal handling ===

    def close_modal_or_popup(self) -> bool:
        self.logger.debug("❌ Closing popup/modal")
        
        if self._find_and_click(self.selectors.close_button, timeout=2):
            self._human_like_delay('click')
            return True
        
        if self._find_and_click(self.selectors.back_button, timeout=2):
            self._human_like_delay('click')
            return True
        
        self._press_back(1)
        return True

    def _check_and_close_problematic_pages(self) -> None:
        """Vérifie et ferme les pages problématiques après navigation."""
        try:
            result = self.problematic_page_detector.detect_and_handle_problematic_pages()
            if result.get('detected'):
                if result.get('closed'):
                    self.logger.info(f"✅ Popup {result.get('page_type')} fermée automatiquement")
                else:
                    self.logger.warning(f"⚠️ Popup {result.get('page_type')} détectée mais non fermée")
        except Exception as e:
            self.logger.debug(f"Erreur lors de la vérification des popups: {e}")
