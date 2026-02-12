"""Atomic navigation actions for TikTok.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

This module aggregates SearchActions and adds bottom-nav, header-tab,
go_back and open_video_author_profile helpers.  Existing code can
continue to ``from ...atomic.navigation_actions import NavigationActions``
and get every method via a single class.
"""

from loguru import logger

from .search_actions import SearchActions
from ...ui.selectors import (
    NAVIGATION_SELECTORS,
    PROFILE_SELECTORS,
    VIDEO_SELECTORS,
)


class NavigationActions(SearchActions):
    """Backward-compatible aggregate of all atomic navigation actions.
    
    Inherits search actions and adds bottom nav, header tabs, go_back, etc.
    Toutes les actions utilisent des sélecteurs basés sur resource-id/content-desc
    pour garantir la compatibilité multi-résolution.
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-navigation-atomic")
        self.navigation_selectors = NAVIGATION_SELECTORS
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
    
    # === Back / Author Profile ===
    
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
