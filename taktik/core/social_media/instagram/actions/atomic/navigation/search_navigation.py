"""Search-based navigation (profile search, hashtag navigation, content navigation)."""

import time
import random
from typing import Optional
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import DETECTION_SELECTORS, NAVIGATION_SELECTORS, PROFILE_SELECTORS


class SearchNavigationMixin(BaseAction):
    """Mixin: navigate via search (profiles, hashtags) and content navigation (posts, stories, lists)."""

    def navigate_to_profile(self, username: str, deep_link_usage_percentage: int = 90, force_search: bool = False) -> bool:
        """
        Navigate to a user's profile.
        
        Args:
            username: The username to navigate to
            deep_link_usage_percentage: Percentage chance to use deep link (0-100)
                                        Set to 0 to always use search
            force_search: If True, always use search (ignores deep_link_usage_percentage)
            
        Returns:
            True if navigation successful, False otherwise
        """
        self.logger.info(f"🎯 Navigating to profile @{username}")
        
        # Determine navigation method
        if force_search:
            use_deep_link = False
            self.logger.debug("Forced to use search navigation")
        else:
            use_deep_link = random.randint(1, 100) <= deep_link_usage_percentage
        
        if use_deep_link:
            self.logger.debug("Using deep link")
            success = self._navigate_via_deep_link(username)
        else:
            self.logger.debug("Using search")
            success = self._navigate_via_search(username)
        
        if success:
            # Vérifier et fermer les popups problématiques (no extra sleep — deep_link/search already have delays)
            self._check_and_close_problematic_pages()
            return True
        
        # Fallback: try the other method
        if not use_deep_link and not force_search:
            self.logger.debug("Fallback attempt with deep link")
            success = self._navigate_via_deep_link(username)
            if success:
                self._check_and_close_problematic_pages()
                return True
        elif use_deep_link:
            self.logger.debug("Fallback attempt with search")
            success = self._navigate_via_search(username)
            if success:
                self._check_and_close_problematic_pages()
                return True
        
        self.logger.warning(f"Navigation failed to @{username}, but continuing")
        return False

    def _navigate_via_search(self, username: str) -> bool:
        """
        Navigate to a profile using the search feature with human-like typing.
        
        Flow:
        1. Click on search tab (bottom bar)
        2. Click on search bar to activate it
        3. Type username with human-like delays
        4. Wait for results and click on the matching profile
        """
        self.logger.info(f"🔍 Navigating to @{username} via search")
        
        # Step 1: Navigate to search tab
        if not self.navigate_to_search():
            self.logger.error("Cannot access search screen")
            return False
        
        self._human_like_delay('navigation')
        
        # Step 2: Click on search bar to activate it
        # On the explore page, we need to click on the search bar at the top
        search_bar_selectors = NAVIGATION_SELECTORS.explore_search_bar
        
        if not self._find_and_click(search_bar_selectors, timeout=5):
            self.logger.error("Cannot find/click search bar")
            return False
        
        self._human_like_delay('click')
        
        # Wait for keyboard to appear and search field to be active
        time.sleep(0.5)
        
        # Step 3: Type username with human-like delays
        self._type_like_human(username, min_delay=0.05, max_delay=0.12)
        
        # Wait for search results to load
        self._human_like_delay('typing')
        time.sleep(1.5)  # Extra time for Instagram to fetch results
        
        # Step 4: Find and click on the search result
        # The clickable element is the container (row_search_user_container), not the TextView
        # We need to find the container that has the matching username inside
        _container_id = NAVIGATION_SELECTORS.search_result_container_resource_id
        _username_id = NAVIGATION_SELECTORS.search_result_username_resource_id
        search_result_selectors = [
            # BEST: Click on the user container that contains the exact username
            f'//*[@resource-id="{_container_id}"][.//*[@resource-id="{_username_id}" and @text="{username}"]]',
            # Alternative: Container with any descendant matching the username
            f'//*[@resource-id="{_container_id}"][.//*[@text="{username}"]]',
            # Fallback: Click directly on the username TextView
            f'//android.widget.TextView[@resource-id="{_username_id}" and @text="{username}"]',
            # Last resort: Any clickable element with the username
            f'//*[@clickable="true"][.//*[@text="{username}"]]'
        ]
        
        # Wait for results to appear
        if self._wait_for_element(search_result_selectors, timeout=5):
            self.logger.debug(f"🔍 Found search result for @{username}, clicking...")
            if self._find_and_click(search_result_selectors, timeout=3):
                self.logger.debug(f"✅ Clicked on search result for @{username}")
                self._human_like_delay('navigation')
                return self._verify_profile_navigation(username)
            else:
                self.logger.warning(f"Found but could not click on @{username}")
        
        self.logger.warning(f"Could not find @{username} in search results")
        return False

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
            # Use Taktik Keyboard for more reliable typing (especially for # character)
            if not self._type_with_taktik_keyboard(hashtag_query):
                self.logger.warning("Taktik Keyboard failed, falling back to send_keys")
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

    # === Profile verification ===

    def _verify_profile_navigation(self, expected_username: str) -> bool:
        # NOTE: _check_and_close_problematic_pages() removed here - already called by navigate_to_profile()
        
        # === FAST PATH: try the top username selectors directly ===
        # If one exists, we're on a profile screen AND we have the username (2-3 calls max instead of 18)
        _fast_selectors = PROFILE_SELECTORS.username[:3]
        for selector in _fast_selectors:
            try:
                el = self.device.xpath(selector)
                if el.exists:
                    current_username = (el.get_text() or '').strip().replace('@', '')
                    if current_username:
                        expected_clean = self._clean_username(expected_username)
                        current_clean = self._clean_username(current_username)
                        self.logger.debug(f"✅ On profile screen, username: '{current_clean}' vs '{expected_clean}'")
                        return current_clean == expected_clean
            except Exception:
                continue
        
        # === FALLBACK: full check (slower but covers edge cases) ===
        if not self._is_profile_screen():
            self.logger.debug(f"❌ Not on profile screen")
            return False
        
        self.logger.debug(f"✅ On profile screen, verifying username...")
        
        from ..detection_actions import DetectionActions
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
        
        username = self._get_text_from_element(PROFILE_SELECTORS.username)
        return self._clean_username(username) if username else None

    # === Content navigation (lists, posts, stories) ===

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

    def navigate_to_next_post(self) -> bool:
        try:
            self.logger.debug("➡️ Navigating to next post")
            
            self.device.swipe(0.8, 0.5, 0.2, 0.5, 0.3)
            self._human_like_delay('navigation')
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error navigating to next post: {e}")
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
