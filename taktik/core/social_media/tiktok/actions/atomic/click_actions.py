"""Atomic click actions for TikTok.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.
"""

from typing import Optional, Dict, Any, List
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import (
    PROFILE_SELECTORS, 
    VIDEO_SELECTORS, 
    NAVIGATION_SELECTORS,
    INBOX_SELECTORS,
    POPUP_SELECTORS,
)


class ClickActions(BaseAction):
    """Low-level click actions for TikTok UI elements.
    
    Toutes les actions utilisent des sélecteurs basés sur resource-id/content-desc
    pour garantir la compatibilité multi-résolution.
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-click-atomic")
        self.video_selectors = VIDEO_SELECTORS
        self.profile_selectors = PROFILE_SELECTORS
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.inbox_selectors = INBOX_SELECTORS
        self.popup_selectors = POPUP_SELECTORS
    
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
        """Click Like button on video.
        
        Uses resource-id f57 with content-desc "Like video".
        """
        self.logger.debug("❤️ Clicking Like button")
        return self._find_and_click(self.video_selectors.like_button, timeout=3)
    
    def double_tap_like(self) -> bool:
        """Double tap to like video (TikTok specific).
        
        Taps on the video container (gy_ or long_press_layout).
        """
        self.logger.debug("❤️ Double tapping to like")
        try:
            self._double_tap_to_like()
            return True
        except Exception as e:
            self.logger.error(f"Error double tapping: {e}")
            return False
    
    def click_comment_button(self) -> bool:
        """Click Comment button on video.
        
        Uses resource-id dtv with content-desc "Read or add comments".
        """
        self.logger.debug("💬 Clicking Comment button")
        return self._find_and_click(self.video_selectors.comment_button, timeout=5)
    
    def click_share_button(self) -> bool:
        """Click Share button on video.
        
        Uses resource-id f57 with content-desc "Share video".
        """
        self.logger.debug("🔗 Clicking Share button")
        return self._find_and_click(self.video_selectors.share_button, timeout=5)
    
    def click_favorite_button(self) -> bool:
        """Click Favorite button on video.
        
        Uses resource-id guh with content-desc "Add or remove this video from Favourites".
        """
        self.logger.debug("⭐ Clicking Favorite button")
        return self._find_and_click(self.video_selectors.favorite_button, timeout=5)
    
    def click_sound_button(self) -> bool:
        """Click Sound button on video (rotating disc).
        
        Uses resource-id nhe with content-desc "Sound: {sound_name}".
        """
        self.logger.debug("🎵 Clicking Sound button")
        return self._find_and_click(self.video_selectors.sound_button, timeout=5)
    
    def click_creator_profile(self) -> bool:
        """Click on creator's profile image on video.
        
        Uses resource-id yx4 with content-desc "{username} profile".
        """
        self.logger.debug("👤 Clicking Creator profile")
        return self._find_and_click(self.video_selectors.creator_profile_image, timeout=5)
    
    def click_video_follow_button(self) -> bool:
        """Click Follow button on video (under creator profile).
        
        Uses resource-id hi1 with content-desc "Follow {username}".
        """
        self.logger.debug("👤 Clicking Follow button on video")
        return self._find_and_click(self.video_selectors.follow_button, timeout=5)
    
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
    
    # === Popup Actions ===
    
    def close_popup(self) -> bool:
        """Try to close any popup or promotional banner.
        
        Handles various TikTok popups including:
        - "Create shared collections" popup
        - Promotional banners
        - Age verification
        - Notification requests
        """
        self.logger.debug("❌ Trying to close popup")
        
        # Try "Not now" button first (most common for feature popups)
        if self._find_and_click(self.popup_selectors.dismiss_button, timeout=2):
            self.logger.info("✅ Closed popup via 'Not now' button")
            return True
        
        # Try close button (X icon)
        if self._find_and_click(self.popup_selectors.close_button, timeout=2):
            self.logger.info("✅ Closed popup via close button")
            return True
        
        # Try promo close button
        if self._find_and_click(self.popup_selectors.promo_close_button, timeout=2):
            self.logger.info("✅ Closed promo banner")
            return True
        
        return False
    
    def close_collections_popup(self) -> bool:
        """Close the 'Create shared collections with a friend' popup.
        
        This popup appears after favoriting videos.
        """
        self.logger.debug("❌ Trying to close collections popup")
        
        # Try "Not now" button first
        if self._find_and_click(self.popup_selectors.collections_not_now, timeout=2):
            self.logger.info("✅ Closed collections popup via 'Not now'")
            return True
        
        # Try close button (X)
        if self._find_and_click(self.popup_selectors.collections_close, timeout=2):
            self.logger.info("✅ Closed collections popup via X button")
            return True
        
        # Fallback to generic close
        return self.close_popup()
    
    def close_follow_friends_popup(self) -> bool:
        """Close the 'Follow your friends' popup.
        
        This popup appears when TikTok wants to suggest contacts to follow.
        """
        self.logger.debug("❌ Trying to close 'Follow your friends' popup")
        
        # Try close button (X) - resource-id dga
        if self._find_and_click(self.popup_selectors.follow_friends_close, timeout=2):
            self.logger.info("✅ Closed 'Follow your friends' popup")
            return True
        
        # Try direct uiautomator2 selector (more reliable)
        try:
            close_elem = self.device(description='Close')
            if close_elem.exists:
                close_elem.click()
                self._human_like_delay('click')
                self.logger.info("✅ Closed 'Follow your friends' popup via description")
                return True
        except Exception as e:
            self.logger.debug(f"Direct close failed: {e}")
        
        # Fallback to generic close
        return self.close_popup()
    
    def dismiss_notification_banner(self) -> bool:
        """Dismiss notification banner by pressing back or swiping it away.
        
        This banner appears at top: "X sent you new messages" with Reply button.
        We need to dismiss it to avoid accidentally clicking on it.
        """
        self.logger.debug("🔔 Trying to dismiss notification banner")
        
        # Check if banner exists
        if self._element_exists(self.popup_selectors.notification_banner, timeout=0.5):
            self.logger.warning("⚠️ Notification banner detected, dismissing...")
            # Press back to dismiss the banner
            self.device.press("back")
            self._human_like_delay('click')
            return True
        
        return False
    
    def escape_inbox_page(self) -> bool:
        """Escape from Inbox page back to previous screen.
        
        This is called when we accidentally navigated to Inbox.
        """
        self.logger.warning("⚠️ On Inbox page, escaping...")
        
        # Press back to go back to previous screen
        self.device.press("back")
        self._human_like_delay('navigation')
        return True
    
    def close_link_email_popup(self) -> bool:
        """Close the 'Link email' popup by clicking 'Not now'.
        
        This popup asks to link Android email addresses for discovery.
        """
        self.logger.debug("📧 Trying to close 'Link email' popup")
        
        if self._find_and_click(self.popup_selectors.link_email_not_now, timeout=2):
            self.logger.info("✅ Closed 'Link email' popup")
            return True
        
        # Fallback: try pressing back
        self.device.press("back")
        self._human_like_delay('click')
        return True
    
    # === Suggestion Page Actions ===
    
    def click_not_interested(self) -> bool:
        """Click 'Not interested' on suggestion page.
        
        This dismisses the suggestion page and continues the For You feed.
        """
        self.logger.debug("❌ Clicking 'Not interested' on suggestion page")
        
        if self._find_and_click(self.popup_selectors.suggestion_not_interested, timeout=3):
            self.logger.info("✅ Clicked 'Not interested'")
            return True
        
        return False
    
    def click_follow_back(self) -> bool:
        """Click 'Follow back' on suggestion page.
        
        This follows the suggested user and continues the For You feed.
        """
        self.logger.debug("👤 Clicking 'Follow back' on suggestion page")
        
        if self._find_and_click(self.popup_selectors.suggestion_follow_back, timeout=3):
            self.logger.info("✅ Clicked 'Follow back'")
            return True
        
        return False
    
    def close_suggestion_page(self) -> bool:
        """Close suggestion page via X button."""
        self.logger.debug("❌ Closing suggestion page")
        
        if self._find_and_click(self.popup_selectors.suggestion_close, timeout=2):
            self.logger.info("✅ Closed suggestion page")
            return True
        
        return False
    
    def handle_suggestion_page(self, follow_back: bool = False) -> bool:
        """Handle suggestion page based on preference.
        
        Args:
            follow_back: If True, click 'Follow back'. If False, click 'Not interested'.
            
        Returns:
            True if handled successfully, False otherwise.
        """
        if follow_back:
            return self.click_follow_back()
        else:
            return self.click_not_interested()
    
    # === Comments Section Actions ===
    
    def close_comments_section(self) -> bool:
        """Close the comments section if it's open.
        
        This can happen accidentally when scrolling and clicking on the comment input area.
        Uses back button as primary method since it's more reliable.
        """
        self.logger.debug("❌ Closing comments section")
        
        # Try close button first
        if self._find_and_click(self.popup_selectors.comments_close_button, timeout=2):
            self.logger.info("✅ Closed comments section via close button")
            return True
        
        # Fallback: use back button/gesture
        try:
            self.device.press("back")
            self._human_like_delay('click')
            self.logger.info("✅ Closed comments section via back button")
            return True
        except Exception as e:
            self.logger.warning(f"Failed to close comments section: {e}")
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
    
    def close_system_popup(self) -> bool:
        """Close Android system popups that may block the app.
        
        This handles popups like:
        - Input method selection ("Sélectionnez le mode de saisie" / "Choose input method")
        - Permission dialogs (contacts, notifications, etc.) - auto-deny
        - System alerts
        
        Returns:
            True if a popup was closed, False otherwise.
        """
        self.logger.debug("🔍 Checking for system popups")
        
        try:
            # Check for permission dialogs and DENY them (FR + EN)
            # These are Android permission requests that we should refuse
            deny_button_selectors = [
                # Package installer (contacts, storage, etc.) - most common
                '//*[@resource-id="com.android.packageinstaller:id/permission_deny_button"]',
                # Permission controller variants
                '//*[@resource-id="com.android.permissioncontroller:id/permission_deny_button"]',
                '//*[@resource-id="com.google.android.permissioncontroller:id/permission_deny_button"]',
                # French text variants
                '//*[@text="REFUSER"][@clickable="true"]',
                '//*[@text="Refuser"][@clickable="true"]',
                '//*[@text="Ne pas autoriser"][@clickable="true"]',
                '//*[@text="Non"][@clickable="true"]',
                # English text variants
                '//*[@text="DENY"][@clickable="true"]',
                '//*[@text="Deny"][@clickable="true"]',
                '//*[@text="Don\'t allow"][@clickable="true"]',
                '//*[@text="DON\'T ALLOW"][@clickable="true"]',
                '//*[@text="No"][@clickable="true"]',
                '//*[@text="NO"][@clickable="true"]',
            ]
            
            if self._find_and_click(deny_button_selectors, timeout=0.5):
                self.logger.warning("⚠️ Permission popup detected, denied automatically")
                self._human_like_delay('click')
                return True
            
            # Check for input method selection popup (package: android)
            input_method_selectors = [
                '//*[@resource-id="android:id/alertTitle"][contains(@text, "saisie")]',
                '//*[@resource-id="android:id/alertTitle"][contains(@text, "input")]',
                '//*[@resource-id="android:id/alertTitle"][contains(@text, "keyboard")]',
                '//*[@resource-id="android:id/alertTitle"][contains(@text, "Keyboard")]',
                '//*[@resource-id="android:id/select_dialog_listview"]',
            ]
            
            if self._element_exists(input_method_selectors, timeout=0.5):
                self.logger.warning("⚠️ System input method popup detected, pressing back")
                self.device.press("back")
                self._human_like_delay('click')
                return True
            
            # Check for generic Android system dialogs
            system_dialog_selectors = [
                '//*[@package="android"][@resource-id="android:id/parentPanel"]',
            ]
            
            if self._element_exists(system_dialog_selectors, timeout=0.5):
                self.logger.warning("⚠️ System dialog detected, pressing back")
                self.device.press("back")
                self._human_like_delay('click')
                return True
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error checking system popups: {e}")
            return False
