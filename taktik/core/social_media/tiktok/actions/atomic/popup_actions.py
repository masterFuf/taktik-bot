"""Atomic popup/overlay actions for TikTok.

Extracted from click_actions.py — contains only popup-related actions
(close popups, dismiss banners, handle suggestions, close comments, system popups).

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.
"""

from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import POPUP_SELECTORS


class PopupActions(BaseAction):
    """Low-level actions to close TikTok popups, overlays, and system dialogs."""
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-popup-atomic")
        self.popup_selectors = POPUP_SELECTORS
    
    # === Generic Popup Actions ===
    
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
    
    def dismiss_notification_banner(self, force_swipe: bool = False) -> bool:
        """Dismiss notification banner by swiping it away.
        
        This banner appears at top: "X sent you new messages" with Reply button.
        We need to dismiss it to avoid accidentally clicking on it.
        
        Args:
            force_swipe: If True, swipe the top area even if banner is not detected
                         (useful as a preventive measure before critical clicks).
        """
        self.logger.debug("🔔 Trying to dismiss notification banner")
        
        detected = self._element_exists(self.popup_selectors.notification_banner, timeout=0.5)
        
        if detected or force_swipe:
            if detected:
                self.logger.warning("⚠️ Notification banner detected, swiping away...")
            else:
                self.logger.debug("🔔 Preventive swipe on notification area")
            
            # Swipe the banner upward to dismiss it
            try:
                w, h = self.device.get_screen_size()
                # Swipe from top area upward to dismiss the banner
                self.device.swipe_coordinates(w // 2, int(h * 0.08), w // 2, 0, duration=0.15)
                import time
                time.sleep(0.5)
            except Exception as e:
                self.logger.debug(f"Swipe dismiss failed: {e}")
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
    
    # === System Popup Actions ===
    
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
            if self._find_and_click(self.popup_selectors.system_deny_button, timeout=0.5):
                self.logger.warning("⚠️ Permission popup detected, denied automatically")
                self._human_like_delay('click')
                return True
            
            # Check for input method selection popup (package: android)
            if self._element_exists(self.popup_selectors.system_input_method_popup, timeout=0.5):
                self.logger.warning("⚠️ System input method popup detected, pressing back")
                self.device.press("back")
                self._human_like_delay('click')
                return True
            
            # Check for generic Android system dialogs
            if self._element_exists(self.popup_selectors.system_dialog, timeout=0.5):
                self.logger.warning("⚠️ System dialog detected, pressing back")
                self.device.press("back")
                self._human_like_delay('click')
                return True
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error checking system popups: {e}")
            return False
