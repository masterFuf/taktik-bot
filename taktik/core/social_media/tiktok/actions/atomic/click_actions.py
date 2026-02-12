"""Atomic click actions for TikTok.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

This module aggregates VideoActions, PopupActions and adds profile + navigation
click helpers.  Existing code can continue to ``from ...atomic.click_actions import ClickActions``
and get every method via a single class.
"""

from loguru import logger

from ..core.base_action import BaseAction
from .video_actions import VideoActions
from .popup_actions import PopupActions
from ...ui.selectors import (
    PROFILE_SELECTORS, 
    NAVIGATION_SELECTORS,
    INBOX_SELECTORS,
)


class ClickActions(VideoActions, PopupActions):
    """Backward-compatible aggregate of all atomic click actions.
    
    Inherits video + popup actions and adds profile + navigation methods.
    Toutes les actions utilisent des sélecteurs basés sur resource-id/content-desc
    pour garantir la compatibilité multi-résolution.
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-click-atomic")
        self.profile_selectors = PROFILE_SELECTORS
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.inbox_selectors = INBOX_SELECTORS
    
    # === Profile Actions ===
    
    def click_follow_button(self) -> bool:
        """Click Follow button on profile."""
        self.logger.debug("👤 Clicking Follow button")
        
        if self._find_and_click(PROFILE_SELECTORS.follow_button, timeout=5):
            return True
        
        self.logger.warning("Follow button not found")
        return False
    
    def click_unfollow_button(self) -> bool:
        """Click Following/Unfollow button on profile."""
        self.logger.debug("👤 Clicking Unfollow button")
        
        if self._find_and_click(PROFILE_SELECTORS.following_button, timeout=5):
            return True
        
        self.logger.warning("Unfollow button not found")
        return False
    
    def click_message_button(self) -> bool:
        """Click Message button on profile."""
        self.logger.debug("💬 Clicking Message button")
        
        if self._find_and_click(PROFILE_SELECTORS.message_button, timeout=5):
            return True
        
        self.logger.warning("Message button not found")
        return False
    
    # === Navigation Actions ===
    
    def click_home_tab(self) -> bool:
        """Click Home tab in bottom navigation.
        
        Uses resource-id mkq with content-desc "Home".
        """
        self.logger.debug("🏠 Clicking Home tab")
        return self._find_and_click(self.navigation_selectors.home_tab, timeout=3)
    
    def click_friends_tab(self) -> bool:
        """Click Friends tab in bottom navigation.
        
        Uses resource-id mkp with content-desc "Friends".
        """
        self.logger.debug("👥 Clicking Friends tab")
        return self._find_and_click(self.navigation_selectors.friends_tab, timeout=3)
    
    def click_create_button(self) -> bool:
        """Click Create button in bottom navigation.
        
        Uses resource-id mkn with content-desc "Create".
        """
        self.logger.debug("➕ Clicking Create button")
        return self._find_and_click(self.navigation_selectors.create_button, timeout=3)
    
    def click_inbox_tab(self) -> bool:
        """Click Inbox tab in bottom navigation.
        
        Uses resource-id mkr with content-desc "Inbox".
        """
        self.logger.debug("📥 Clicking Inbox tab")
        return self._find_and_click(self.navigation_selectors.inbox_tab, timeout=3)
    
    def click_profile_tab(self) -> bool:
        """Click Profile tab in bottom navigation.
        
        Uses resource-id mks with content-desc "Profile".
        """
        self.logger.debug("👤 Clicking Profile tab")
        return self._find_and_click(self.navigation_selectors.profile_tab, timeout=3)
    
    def click_search_button(self) -> bool:
        """Click Search button in header.
        
        Uses resource-id irz with content-desc "Search".
        """
        self.logger.debug("🔍 Clicking Search button")
        return self._find_and_click(self.navigation_selectors.search_button, timeout=3)
    
    def click_back_button(self) -> bool:
        """Click back button."""
        self.logger.debug("⬅️ Clicking Back button")
        
        if self._find_and_click(self.navigation_selectors.back_button, timeout=3):
            return True
        
        # Fallback: use hardware back button
        try:
            self._press_back()
            return True
        except Exception as e:
            self.logger.error(f"Error pressing back: {e}")
            return False
    
    # === Header Tabs (For You page) ===
    
    def click_for_you_tab(self) -> bool:
        """Click For You tab in header."""
        self.logger.debug("📱 Clicking For You tab")
        return self._find_and_click(self.navigation_selectors.for_you_tab, timeout=3)
    
    def click_following_tab(self) -> bool:
        """Click Following tab in header."""
        self.logger.debug("👥 Clicking Following tab")
        return self._find_and_click(self.navigation_selectors.following_tab, timeout=3)
    
    def click_explore_tab(self) -> bool:
        """Click Explore tab in header."""
        self.logger.debug("🔍 Clicking Explore tab")
        return self._find_and_click(self.navigation_selectors.explore_tab, timeout=3)
    
    def click_live_tab(self) -> bool:
        """Click LIVE tab in header."""
        self.logger.debug("🔴 Clicking LIVE tab")
        return self._find_and_click(self.navigation_selectors.live_tab, timeout=3)
    
    # === Helper Methods ===
    
    def follow_user(self, username: str) -> bool:
        """Follow a user."""
        try:
            self.logger.info(f"👤 Attempting to follow @{username}")
            
            if self.click_follow_button():
                self.logger.success(f"✅ Followed @{username}")
                return True
            
            self.logger.warning(f"❌ Failed to follow @{username}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error following @{username}: {e}")
            return False
    
    def unfollow_user(self, username: str) -> bool:
        """Unfollow a user."""
        try:
            self.logger.info(f"👤 Attempting to unfollow @{username}")
            
            if self.click_unfollow_button():
                # May need to confirm unfollow
                self._human_like_delay('click')
                
                # Look for confirmation button
                confirm_selectors = [
                    '//android.widget.Button[contains(@text, "Unfollow")]',
                    '//android.widget.Button[contains(@text, "Se désabonner")]'
                ]
                
                if self._element_exists(confirm_selectors, timeout=2):
                    if self._find_and_click(confirm_selectors, timeout=3):
                        self.logger.success(f"✅ Unfollowed @{username}")
                        return True
                else:
                    # No confirmation needed
                    self.logger.success(f"✅ Unfollowed @{username}")
                    return True
            
            self.logger.warning(f"❌ Failed to unfollow @{username}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error unfollowing @{username}: {e}")
            return False
