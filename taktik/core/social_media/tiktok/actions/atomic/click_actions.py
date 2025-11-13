"""Atomic click actions for TikTok."""

from typing import Optional, Dict, Any, List
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import PROFILE_SELECTORS, VIDEO_SELECTORS, NAVIGATION_SELECTORS


class ClickActions(BaseAction):
    """Low-level click actions for TikTok UI elements."""
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-click-atomic")
    
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
    
    # === Video Interaction Actions ===
    
    def click_like_button(self) -> bool:
        """Click Like button on video."""
        self.logger.debug("❤️ Clicking Like button")
        
        return self._find_and_click(VIDEO_SELECTORS.like_button, timeout=3)
    
    def double_tap_like(self) -> bool:
        """Double tap to like video (TikTok specific)."""
        self.logger.debug("❤️ Double tapping to like")
        
        try:
            self._double_tap_to_like()
            return True
        except Exception as e:
            self.logger.error(f"Error double tapping: {e}")
            return False
    
    def click_comment_button(self) -> bool:
        """Click Comment button on video."""
        self.logger.debug("💬 Clicking Comment button")
        
        if self._find_and_click(VIDEO_SELECTORS.comment_button, timeout=5):
            return True
        
        self.logger.warning("Comment button not found")
        return False
    
    def click_share_button(self) -> bool:
        """Click Share button on video."""
        self.logger.debug("🔗 Clicking Share button")
        
        if self._find_and_click(VIDEO_SELECTORS.share_button, timeout=5):
            return True
        
        self.logger.warning("Share button not found")
        return False
    
    def click_favorite_button(self) -> bool:
        """Click Favorite button on video."""
        self.logger.debug("⭐ Clicking Favorite button")
        
        if self._find_and_click(VIDEO_SELECTORS.favorite_button, timeout=5):
            return True
        
        self.logger.warning("Favorite button not found")
        return False
    
    # === Navigation Actions ===
    
    def click_home_tab(self) -> bool:
        """Click Home tab in bottom navigation."""
        self.logger.debug("🏠 Clicking Home tab")
        
        return self._find_and_click(NAVIGATION_SELECTORS.home_tab, timeout=3)
    
    def click_discover_tab(self) -> bool:
        """Click Discover tab in bottom navigation."""
        self.logger.debug("🔍 Clicking Discover tab")
        
        return self._find_and_click(NAVIGATION_SELECTORS.discover_tab, timeout=3)
    
    def click_inbox_tab(self) -> bool:
        """Click Inbox tab in bottom navigation."""
        self.logger.debug("📥 Clicking Inbox tab")
        
        return self._find_and_click(NAVIGATION_SELECTORS.inbox_tab, timeout=3)
    
    def click_profile_tab(self) -> bool:
        """Click Profile tab in bottom navigation."""
        self.logger.debug("👤 Clicking Profile tab")
        
        return self._find_and_click(NAVIGATION_SELECTORS.profile_tab, timeout=3)
    
    def click_back_button(self) -> bool:
        """Click back button."""
        self.logger.debug("⬅️ Clicking Back button")
        
        if self._find_and_click(NAVIGATION_SELECTORS.back_button, timeout=3):
            return True
        
        # Fallback: use hardware back button
        try:
            self._press_back()
            return True
        except Exception as e:
            self.logger.error(f"Error pressing back: {e}")
            return False
    
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
    
    def like_video(self) -> bool:
        """Like current video (try button first, then double tap)."""
        try:
            self.logger.info("❤️ Attempting to like video")
            
            # Try clicking like button first
            if self.click_like_button():
                self.logger.success("✅ Video liked via button")
                return True
            
            # Fallback: double tap
            if self.double_tap_like():
                self.logger.success("✅ Video liked via double tap")
                return True
            
            self.logger.warning("❌ Failed to like video")
            return False
            
        except Exception as e:
            self.logger.error(f"Error liking video: {e}")
            return False
