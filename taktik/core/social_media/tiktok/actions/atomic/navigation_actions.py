"""Atomic navigation actions for TikTok.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.
"""

from typing import Optional, Dict, Any
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import (
    NAVIGATION_SELECTORS, 
    SEARCH_SELECTORS, 
    PROFILE_SELECTORS,
    VIDEO_SELECTORS,
    DETECTION_SELECTORS,
)


class NavigationActions(BaseAction):
    """Low-level navigation actions for TikTok.
    
    Toutes les actions utilisent des sélecteurs basés sur resource-id/content-desc
    pour garantir la compatibilité multi-résolution.
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-navigation-atomic")
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.search_selectors = SEARCH_SELECTORS
        self.profile_selectors = PROFILE_SELECTORS
        self.video_selectors = VIDEO_SELECTORS
    
    # === Bottom Navigation Bar ===
    
    def navigate_to_home(self) -> bool:
        """Navigate to Home feed (For You).
        
        Uses resource-id mkq with content-desc "Home".
        """
        self.logger.info("🏠 Navigating to Home")
        
        if self._find_and_click(self.navigation_selectors.home_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Home")
            return True
        
        self.logger.warning("❌ Failed to navigate to Home")
        return False
    
    def navigate_to_friends(self) -> bool:
        """Navigate to Friends page.
        
        Uses resource-id mkp with content-desc "Friends".
        """
        self.logger.info("👥 Navigating to Friends")
        
        if self._find_and_click(self.navigation_selectors.friends_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Friends")
            return True
        
        self.logger.warning("❌ Failed to navigate to Friends")
        return False
    
    def navigate_to_inbox(self) -> bool:
        """Navigate to Inbox.
        
        Uses resource-id mkr with content-desc "Inbox".
        """
        self.logger.info("📥 Navigating to Inbox")
        
        if self._find_and_click(self.navigation_selectors.inbox_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Inbox")
            return True
        
        self.logger.warning("❌ Failed to navigate to Inbox")
        return False
    
    def navigate_to_profile(self) -> bool:
        """Navigate to own profile.
        
        Uses resource-id mks with content-desc "Profile".
        """
        self.logger.info("👤 Navigating to Profile")
        
        if self._find_and_click(self.navigation_selectors.profile_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Profile")
            return True
        
        self.logger.warning("❌ Failed to navigate to Profile")
        return False
    
    # === Header Tabs ===
    
    def navigate_to_for_you(self) -> bool:
        """Navigate to For You tab in header."""
        self.logger.info("📱 Navigating to For You")
        
        if self._find_and_click(self.navigation_selectors.for_you_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to For You")
            return True
        
        self.logger.warning("❌ Failed to navigate to For You")
        return False
    
    def navigate_to_following_feed(self) -> bool:
        """Navigate to Following tab in header."""
        self.logger.info("👥 Navigating to Following feed")
        
        if self._find_and_click(self.navigation_selectors.following_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Following feed")
            return True
        
        self.logger.warning("❌ Failed to navigate to Following feed")
        return False
    
    def navigate_to_explore(self) -> bool:
        """Navigate to Explore tab in header."""
        self.logger.info("🔍 Navigating to Explore")
        
        if self._find_and_click(self.navigation_selectors.explore_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Explore")
            return True
        
        self.logger.warning("❌ Failed to navigate to Explore")
        return False
    
    # === Search & User Navigation ===
    
    def navigate_to_user_profile(self, username: str) -> bool:
        """Navigate to specific user's profile via search."""
        self.logger.info(f"👤 Navigating to @{username}'s profile")
        
        try:
            # First go to home, then click search
            if not self.navigate_to_home():
                return False
            
            # Click search button in header
            if not self._find_and_click(self.navigation_selectors.search_button, timeout=5):
                self.logger.warning("Search button not found")
                return False
            
            self._human_like_delay('click')
            
            # Click search bar
            if not self._find_and_click(self.search_selectors.search_bar, timeout=5):
                self.logger.warning("Search bar not found")
                return False
            
            self._human_like_delay('click')
            
            # Input username
            if not self._input_text(self.search_selectors.search_bar, username, clear_first=True):
                self.logger.warning("Failed to input username")
                return False
            
            self._human_like_delay('typing')
            
            # Click on Users tab
            if self._element_exists(self.search_selectors.users_tab, timeout=3):
                self._find_and_click(self.search_selectors.users_tab, timeout=3)
                self._human_like_delay('click')
            
            # Click on first result (should be exact match)
            first_result_selectors = [
                f'//android.widget.TextView[@text="@{username}"]',
                f'//android.widget.TextView[contains(@text, "{username}")]',
                '(//androidx.recyclerview.widget.RecyclerView//android.view.ViewGroup)[1]'
            ]
            
            if self._find_and_click(first_result_selectors, timeout=5):
                self._human_like_delay('navigation')
                self.logger.success(f"✅ Navigated to @{username}'s profile")
                return True
            
            self.logger.warning(f"❌ Failed to find @{username} in search results")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to @{username}: {e}")
            return False
    
    def search_hashtag(self, hashtag: str) -> bool:
        """Search for a hashtag."""
        self.logger.info(f"🔍 Searching for #{hashtag}")
        
        try:
            # Remove # if present
            hashtag = hashtag.lstrip('#')
            
            # First go to home, then click search
            if not self.navigate_to_home():
                return False
            
            # Click search button in header
            if not self._find_and_click(self.navigation_selectors.search_button, timeout=5):
                self.logger.warning("Search button not found")
                return False
            
            self._human_like_delay('click')
            
            # Click search bar
            if not self._find_and_click(self.search_selectors.search_bar, timeout=5):
                self.logger.warning("Search bar not found")
                return False
            
            self._human_like_delay('click')
            
            # Input hashtag
            search_query = f"#{hashtag}"
            if not self._input_text(self.search_selectors.search_bar, search_query, clear_first=True):
                self.logger.warning("Failed to input hashtag")
                return False
            
            self._human_like_delay('typing')
            
            # Click on Hashtags tab
            if self._element_exists(self.search_selectors.hashtags_tab, timeout=3):
                self._find_and_click(self.search_selectors.hashtags_tab, timeout=3)
                self._human_like_delay('click')
            
            # Click on first hashtag result
            first_hashtag_selectors = [
                f'//android.widget.TextView[@text="#{hashtag}"]',
                f'//android.widget.TextView[contains(@text, "#{hashtag}")]',
                '(//androidx.recyclerview.widget.RecyclerView//android.view.ViewGroup)[1]'
            ]
            
            if self._find_and_click(first_hashtag_selectors, timeout=5):
                self._human_like_delay('navigation')
                self.logger.success(f"✅ Navigated to #{hashtag}")
                return True
            
            self.logger.warning(f"❌ Failed to find #{hashtag} in search results")
            return False
            
        except Exception as e:
            self.logger.error(f"Error searching for #{hashtag}: {e}")
            return False
    
    def go_back(self) -> bool:
        """Go back to previous screen."""
        self.logger.debug("⬅️ Going back")
        
        try:
            # Try UI back button first
            if self._find_and_click(self.navigation_selectors.back_button, timeout=2):
                self._human_like_delay('navigation')
                return True
            
            # Fallback: hardware back button
            self._press_back()
            return True
            
        except Exception as e:
            self.logger.error(f"Error going back: {e}")
            return False
    
    def open_video_author_profile(self) -> bool:
        """Open profile of current video's author.
        
        Uses resource-id title for username or yx4 for profile image.
        """
        self.logger.info("👤 Opening video author's profile")
        
        try:
            # Try clicking on author username first
            if self._find_and_click(self.video_selectors.author_username, timeout=5):
                self._human_like_delay('navigation')
                self.logger.success("✅ Opened author's profile via username")
                return True
            
            # Fallback: click on profile image
            if self._find_and_click(self.video_selectors.creator_profile_image, timeout=5):
                self._human_like_delay('navigation')
                self.logger.success("✅ Opened author's profile via image")
                return True
            
            self.logger.warning("❌ Failed to open author's profile")
            return False
            
        except Exception as e:
            self.logger.error(f"Error opening author profile: {e}")
            return False
