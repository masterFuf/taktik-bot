"""Atomic navigation actions for Instagram."""

import time
import random
import subprocess
from typing import Optional, Dict, Any
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import DETECTION_SELECTORS, NAVIGATION_SELECTORS, PROFILE_SELECTORS
from ...ui.detectors.problematic_page import ProblematicPageDetector


class NavigationActions(BaseAction):
        
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-navigation-atomic")
        self.detection_selectors = DETECTION_SELECTORS
        self.selectors = NAVIGATION_SELECTORS
        self.profile_selectors = PROFILE_SELECTORS
        self.problematic_page_detector = ProblematicPageDetector(device, debug_mode=False)
    
    def _get_device_serial(self) -> str:
        try:
            device_serial = getattr(self.device.device, 'serial', None)
            if not device_serial:
                device_info = getattr(self.device.device, '_device_info', {})
                device_serial = device_info.get('serial', 'emulator-5554')
            
            if not device_serial:
                self.logger.warning("⚠️ Device ID not found, using emulator-5554")
                device_serial = "emulator-5554"
                
        except Exception as e:
            self.logger.warning(f"⚠️ Device ID error: {e}, using emulator-5554")
            device_serial = "emulator-5554"
        
        return device_serial
    
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
    
    def navigate_to_hashtag(self, hashtag: str) -> bool:
        try:
            self.logger.debug(f"🏷️ Navigating to hashtag #{hashtag}")
            
            if not self.navigate_to_search():
                self.logger.error("Cannot navigate to search screen")
                return False
            
            search_bar_clicked = False
            for selector in self.detection_selectors.hashtag_search_bar_selectors:
                if self._find_and_click(selector, timeout=2):
                    search_bar_clicked = True
                    break
            
            if not search_bar_clicked:
                self.logger.error("Cannot click on search bar")
                return False
            
            self._human_like_delay('input')
            
            hashtag_query = f"#{hashtag}"
            self.device.send_keys(hashtag_query)
            self._human_like_delay('typing')
            time.sleep(2)
            hashtag_result_selectors = [
                f'//android.widget.TextView[@text="#{hashtag}"]',
                f'//*[contains(@text, "#{hashtag}")]',
                f'//*[contains(@content-desc, "#{hashtag}")]',
                '//android.widget.TextView[contains(@text, "publications")]/../..',
                '//android.widget.TextView[contains(@text, "posts")]/../..'
            ]
            
            hashtag_clicked = False
            for selector in hashtag_result_selectors:
                if self._find_and_click(selector, timeout=3):
                    hashtag_clicked = True
                    self.logger.debug(f"Clicked on hashtag with selector: {selector}")
                    break
            
            if not hashtag_clicked:
                self.logger.error(f"Cannot click on hashtag #{hashtag}")
                return False
            
            self._human_like_delay('navigation')
            time.sleep(2)
            
            hashtag_specific = f'//*[contains(@text, "#{hashtag}")]'
            if self.device.xpath(hashtag_specific).exists:
                self.logger.debug(f"✅ Hashtag page #{hashtag} loaded successfully")
                return True
            
            for indicator in self.detection_selectors.hashtag_page_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"✅ Hashtag page #{hashtag} loaded successfully")
                    return True
            
            self.logger.warning(f"Hashtag page #{hashtag} might be loaded but no confirmation")
            return True
            
        except Exception as e:
            self.logger.error(f"Error navigating to hashtag #{hashtag}: {e}")
            return False
    
    def navigate_to_profile_tab(self) -> bool:
        self.logger.debug("👤 Navigating to profile tab")
        
        max_attempts = 3
        
        for attempt in range(max_attempts):
            from .detection_actions import DetectionActions
            detection = DetectionActions(self.device)
            
            if detection.is_on_own_profile():
                self.logger.debug("✅ Already on own profile")
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
        return False
    
    def navigate_to_profile(self, username: str, deep_link_usage_percentage: int = 90) -> bool:
        self.logger.info(f"🎯 Navigating to profile @{username}")
        
        use_deep_link = random.randint(1, 100) <= deep_link_usage_percentage
        
        if use_deep_link:
            self.logger.debug("Using deep link")
            success = self._navigate_via_deep_link(username)
        else:
            self.logger.debug("Using search")
            success = self._navigate_via_search(username)
        
        if success:
            self._random_sleep()
            # Vérifier et fermer les popups problématiques
            self._check_and_close_problematic_pages()
            return True
        
        if not use_deep_link:
            self.logger.debug("Fallback attempt with deep link")
            success = self._navigate_via_deep_link(username)
            if success:
                self._random_sleep()
                # Vérifier et fermer les popups problématiques
                self._check_and_close_problematic_pages()
                return True
        
        self.logger.warning(f"Navigation failed to @{username}, but continuing")
        return False
    
    def _navigate_via_deep_link(self, username: str, max_attempts: int = 3) -> bool:
        device_serial = self._get_device_serial()
        self.logger.debug(f"🔧 Using device: {device_serial}")
        
        for attempt in range(2):
            try:
                self.logger.debug(f"Attempt {attempt + 1}/2 - Deep link to @{username}")
                
                deep_link_url = f"https://www.instagram.com/{username}/"
                cmd = [
                    'adb', '-s', device_serial, 'shell', 'am', 'start',
                    '-W', '-a', 'android.intent.action.VIEW',
                    '-d', deep_link_url,
                    'com.instagram.android'
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    self.logger.debug("Deep link executed successfully")
                    self._human_like_delay('navigation')
                    
                    if self._verify_profile_navigation(username):
                        return True
                else:
                    self.logger.debug(f"Deep link failed: {result.stderr}")
                
            except subprocess.TimeoutExpired:
                self.logger.debug("Timeout during deep link execution")
            except Exception as e:
                self.logger.debug(f"Deep link error: {e}")
            
            if attempt < max_attempts - 1:
                self._human_like_delay('navigation')
        
        return False
    
    def _navigate_via_search(self, username: str) -> bool:
        if not self.navigate_to_search():
            self.logger.error("Cannot access search screen")
            return False
        
        if not self._find_and_click(self.detection_selectors.search_bar_selectors, timeout=5):
            self.logger.error("Cannot find search bar")
            return False
        
        self._human_like_delay('click')
        self.device.send_keys(username)
        self._human_like_delay('typing')
        
        search_result = f'//android.widget.TextView[@text="{username}"]'
        if self._wait_for_element(search_result, timeout=5):
            if self._find_and_click(search_result, timeout=3):
                self._human_like_delay('navigation')
                return self._verify_profile_navigation(username)
        
        return False
    
    def open_followers_list(self) -> bool:
        self.logger.debug("👥 Opening followers list")
        
        if self._find_and_click(self.profile_selectors.followers_link, timeout=5):
            self._human_like_delay('navigation')
            
            # Attendre que la liste se charge (Instagram peut être lent)
            time.sleep(2)
            
            # Vérifier si la liste est ouverte
            is_open = self._is_followers_list_open()
            if is_open:
                self.logger.debug("✅ Followers list opened successfully")
            else:
                self.logger.warning("⚠️ Followers list may not be fully loaded, but continuing...")
                # Même si la détection échoue, on continue (la liste peut être ouverte mais avec des sélecteurs différents)
                return True
            
            return is_open
        
        return False
    
    def open_following_list(self) -> bool:
        self.logger.debug("👥 Opening following list")
        
        if self._find_and_click(self.profile_selectors.following_link, timeout=5):
            self._human_like_delay('navigation')
            return self._is_following_list_open()
        
        return False
    
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
    
    def _verify_profile_navigation(self, expected_username: str) -> bool:
        # D'abord vérifier et fermer les popups problématiques
        self._check_and_close_problematic_pages()
        
        if not self._is_profile_screen():
            self.logger.debug(f"❌ Not on profile screen")
            return False
        
        self.logger.debug(f"✅ On profile screen, verifying username...")
        
        from .detection_actions import DetectionActions
        detection = DetectionActions(self.device)
        current_username = detection.get_username_from_profile()
        
        if current_username:
            current_username = self._clean_username(current_username)
            expected_clean = self._clean_username(expected_username)
            self.logger.debug(f"Username comparison: '{current_username}' vs '{expected_clean}'")
            return current_username == expected_clean
        
        self.logger.warning(f"⚠️ Could not extract username from profile")
        return True
    
    def is_on_profile(self, username: str) -> bool:
        return self._verify_profile_navigation(username)
    
    def get_current_username(self) -> Optional[str]:
        if not self._is_profile_screen():
            return None
        
        from ...ui.selectors import PROFILE_SELECTORS
        username = self._get_text_from_element(PROFILE_SELECTORS.username)
        return self._clean_username(username) if username else None
    
    def navigate_to_next_post(self) -> bool:
        try:
            self.logger.debug("➡️ Navigating to next post")
            
            self.device.swipe(0.8, 0.5, 0.2, 0.5, 0.3)
            self._human_like_delay('navigation')
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error navigating to next post: {e}")
            return False
    
    def navigate_to_post_via_deep_link(self, post_url: str) -> bool:
        try:
            import subprocess
            
            self.logger.info(f"🔗 Navigating to post via deep link: {post_url}")
            
            device_serial = self._get_device_serial()
            adb_command = [
                "adb", "-s", device_serial,
                "shell", "am", "start",
                "-W", "-a", "android.intent.action.VIEW",
                "-d", post_url,
                "com.instagram.android"
            ]
            
            result = subprocess.run(adb_command, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                self.logger.error(f"❌ ADB error opening post: {result.stderr}")
                return False
                
            self._human_like_delay('page_load')
            
            for selector in self.detection_selectors.post_error_indicators:
                try:
                    if self._wait_for_element(selector, timeout=2, silent=True):
                        self.logger.error(f"❌ Post inaccessible: {post_url}")
                        self._press_back()
                        return False
                except Exception:
                    continue
            
            for indicator in self.detection_selectors.post_screen_indicators:
                if self._wait_for_element(indicator, timeout=3, silent=True):
                    self.logger.success(f"✅ Successfully navigated to post")
                    return True
            
            self.logger.warning(f"⚠️ Navigation to post uncertain: {post_url}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error navigating to post via deep link: {e}")
            return False
    
    def navigate_to_next_story(self) -> bool:
        try:
            screen_width = self.device.info.get('displayWidth', 1080)
            screen_height = self.device.info.get('displayHeight', 1920)
            
            tap_x = int(screen_width * 0.75)
            tap_y = int(screen_height * 0.5)
            
            self.logger.debug(f"👆 Tap for next story: ({tap_x}, {tap_y})")
            self.device.click(tap_x, tap_y)
            
            self._human_like_delay('story_transition')
            
            for indicator in self.detection_selectors.story_viewer_indicators:
                if self._wait_for_element(indicator, timeout=2):
                    self.logger.debug("✅ Still in stories")
                    return True
            
            self.logger.debug("ℹ️ No more stories or end of stories")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to next story: {e}")
            return False
    
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
