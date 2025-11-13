"""Atomic navigation actions for TikTok."""

from typing import Optional, Dict, Any
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import NAVIGATION_SELECTORS, SEARCH_SELECTORS, PROFILE_SELECTORS


class NavigationActions(BaseAction):
    """Low-level navigation actions for TikTok."""
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-navigation-atomic")
    
    def navigate_to_home(self) -> bool:
        """Navigate to Home feed."""
        self.logger.info("🏠 Navigating to Home")
        
        if self._find_and_click(NAVIGATION_SELECTORS.home_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Home")
            return True
        
        self.logger.warning("❌ Failed to navigate to Home")
        return False
    
    def navigate_to_discover(self) -> bool:
        """Navigate to Discover page."""
        self.logger.info("🔍 Navigating to Discover")
        
        if self._find_and_click(NAVIGATION_SELECTORS.discover_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Discover")
            return True
        
        self.logger.warning("❌ Failed to navigate to Discover")
        return False
    
    def navigate_to_inbox(self) -> bool:
        """Navigate to Inbox."""
        self.logger.info("📥 Navigating to Inbox")
        
        if self._find_and_click(NAVIGATION_SELECTORS.inbox_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Inbox")
            return True
        
        self.logger.warning("❌ Failed to navigate to Inbox")
        return False
    
    def navigate_to_profile(self) -> bool:
        """Navigate to own profile."""
        self.logger.info("👤 Navigating to Profile")
        
        if self._find_and_click(NAVIGATION_SELECTORS.profile_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Profile")
            return True
        
        self.logger.warning("❌ Failed to navigate to Profile")
        return False
    
    def navigate_to_user_profile(self, username: str) -> bool:
        """Navigate to specific user's profile via search."""
        self.logger.info(f"👤 Navigating to @{username}'s profile")
        
        try:
            # Go to Discover page
            if not self.navigate_to_discover():
                return False
            
            # Click search bar
            if not self._find_and_click(SEARCH_SELECTORS.search_bar, timeout=5):
                self.logger.warning("Search bar not found")
                return False
            
            self._human_like_delay('click')
            
            # Input username
            if not self._input_text(SEARCH_SELECTORS.search_bar, username, clear_first=True):
                self.logger.warning("Failed to input username")
                return False
            
            self._human_like_delay('typing')
            
            # Click on Users tab
            if self._element_exists(SEARCH_SELECTORS.users_tab, timeout=3):
                self._find_and_click(SEARCH_SELECTORS.users_tab, timeout=3)
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
            
            # Go to Discover page
            if not self.navigate_to_discover():
                return False
            
            # Click search bar
            if not self._find_and_click(SEARCH_SELECTORS.search_bar, timeout=5):
                self.logger.warning("Search bar not found")
                return False
            
            self._human_like_delay('click')
            
            # Input hashtag
            search_query = f"#{hashtag}"
            if not self._input_text(SEARCH_SELECTORS.search_bar, search_query, clear_first=True):
                self.logger.warning("Failed to input hashtag")
                return False
            
            self._human_like_delay('typing')
            
            # Click on Hashtags tab
            if self._element_exists(SEARCH_SELECTORS.hashtags_tab, timeout=3):
                self._find_and_click(SEARCH_SELECTORS.hashtags_tab, timeout=3)
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
            if self._find_and_click(NAVIGATION_SELECTORS.back_button, timeout=2):
                self._human_like_delay('navigation')
                return True
            
            # Fallback: hardware back button
            self._press_back()
            return True
            
        except Exception as e:
            self.logger.error(f"Error going back: {e}")
            return False
    
    def open_video_author_profile(self) -> bool:
        """Open profile of current video's author."""
        self.logger.info("👤 Opening video author's profile")
        
        try:
            # Click on author username
            if self._find_and_click(VIDEO_SELECTORS.author_username, timeout=5):
                self._human_like_delay('navigation')
                self.logger.success("✅ Opened author's profile")
                return True
            
            self.logger.warning("❌ Failed to open author's profile")
            return False
            
        except Exception as e:
            self.logger.error(f"Error opening author profile: {e}")
            return False
