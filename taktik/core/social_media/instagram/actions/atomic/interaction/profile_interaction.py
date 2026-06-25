"""Profile interaction actions (follow, unfollow, message, follow state detection)."""

from typing import Optional, Dict, Any, List
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS


class ProfileInteractionMixin(BaseAction):
    """Mixin: follow/unfollow, message button, follow state detection, review popup."""

    def click_follow_button(self) -> bool:
        return self._click_button(self.profile_selectors.follow_button, "Follow button", "👤")
    
    def click_unfollow_button(self) -> bool:
        return self._click_button(self.profile_selectors.following_button, "Unfollow button", "👤")

    def click_message_button(self) -> bool:
        return self._click_button(self.profile_selectors.message_button, "Message button", "💌")

    def click_followers_count(self) -> bool:
        return self._click_button(self.profile_selectors.followers_count, "Followers count", "👥")
    
    def click_following_count(self) -> bool:
        return self._click_button(self.profile_selectors.following_count, "Following count", "👥")
    
    def click_posts_count(self) -> bool:
        return self._click_button(self.profile_selectors.posts_count, "Posts count", "📸")

    def is_follow_button_available(self) -> bool:
        return self._is_element_present(self.profile_selectors.follow_button)
    
    def is_unfollow_button_available(self) -> bool:
        return self._is_element_present(self.profile_selectors.following_button)

    # === Follow workflow ===

    def follow_user(self, username: str) -> bool:
        try:
            self.logger.info(f"👤 Attempting to follow @{username}")
            
            # follow_button is a List[str] property — spread it (a bare entry would nest a list
            # inside follow_selectors and make device.xpath() raise "Invalid attr").
            follow_selectors = PROFILE_SELECTORS.advanced_follow_selectors + [
                *PROFILE_SELECTORS.follow_button,
                PROFILE_SELECTORS.follow_buttons,
                PROFILE_SELECTORS.suivre_buttons
            ]
            
            if self._find_and_click(follow_selectors, timeout=5):
                # Vérifier qu'on n'a pas navigué vers la liste des followers
                self._human_like_delay('click')
                
                # Check for "Review this account before following" popup
                if self._handle_review_account_popup():
                    self.logger.info(f"📋 Handled 'Review account' popup for @{username}")
                    self._human_like_delay('click')
                
                if self._verify_follow_success(username):
                    self.logger.info(f"✅ Successfully followed @{username}")
                    # Note: L'événement follow_event est émis par le workflow (followers.py)
                    # pour inclure les données du profil. Ne pas dupliquer ici.
                    return True
                else:
                    self.logger.warning(f"❌ Clicked but not on the right button for @{username}")
                    return False
            else:
                self.logger.warning(f"❌ Follow button not found for @{username}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to follow @{username}: {e}")
            return False
    
    def _handle_review_account_popup(self) -> bool:
        """
        Handle the "Review this account before following" popup that appears for new accounts.
        Clicks the Follow button in the popup to confirm the follow action.
        
        Returns:
            True if popup was detected and handled, False otherwise
        """
        try:
            # Check if the popup is present
            for indicator in self.popup_selectors.review_account_popup_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.info("📋 'Review this account before following' popup detected")
                    
                    # Click the Follow button in the popup
                    for follow_btn in self.popup_selectors.review_account_follow_button:
                        if self.device.xpath(follow_btn).exists:
                            self.device.xpath(follow_btn).click()
                            self.logger.info("✅ Clicked Follow button in review popup")
                            return True
                    
                    self.logger.warning("⚠️ Review popup detected but Follow button not found")
                    return False
            
            return False
        except Exception as e:
            self.logger.error(f"Error handling review account popup: {e}")
            return False
    
    def _verify_follow_success(self, username: str) -> bool:
        try:
            for indicator in self.detection_selectors.followers_list_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.warning(f"❌ Navigation to list detected for @{username}")
                    self.device.press("back")
                    return False
            
            # Vérifier qu'on est toujours sur un profil
            from ..detection import DetectionActions
            detection = DetectionActions(self.device)
            
            if detection.is_on_profile_screen():
                self.logger.debug(f"✅ Still on profile after follow @{username}")
                return True
            else:
                self.logger.warning(f"❌ Not on profile after follow attempt @{username}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error verifying follow @{username}: {e}")
            return True

    # === Follow button state ===

    def get_follow_button_state(self) -> str:
        """
        Detect the follow button state by checking the button text.
        Returns: 'follow', 'following', 'requested', 'message', or 'unknown'
        
        Optimized: tries resource-id lookup first (1 XPath call → read text)
        instead of iterating 16+ selectors sequentially (~0.5-1s each when absent).
        """
        # === FAST PATH: find button by resource-id, then read its text ===
        try:
            btn = self.device.xpath(PROFILE_SELECTORS.follow_button[0])
            if btn.exists:
                text = (btn.get_text() or '').strip().lower()
                if text:
                    if any(kw in text for kw in ('following', 'abonné', 'suivi')):
                        return 'following'
                    if any(kw in text for kw in ('requested', 'demandé')):
                        return 'requested'
                    if any(kw in text for kw in ('follow', 'suivre')):
                        return 'follow'
                    if any(kw in text for kw in ('message', 'envoyer')):
                        return 'message'
        except Exception:
            pass
        
        # === FALLBACK: check Message button (means we already follow) ===
        if self._is_element_present(self.profile_selectors.message_button):
            return 'message'
        
        return 'unknown'
