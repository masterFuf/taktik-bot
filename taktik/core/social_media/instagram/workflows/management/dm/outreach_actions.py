"""Navigation, follow, DM conversation, message sending for the Outreach workflow."""

import time
from typing import Optional

from taktik.core.shared.input.taktik_keyboard import type_with_taktik_keyboard
from taktik.core.social_media.instagram.actions.atomic.text import dm_composer


class OutreachActionsMixin:
    """Mixin: profile navigation, follow, DM open, message send, back to home."""

    def _navigate_to_dm_inbox(self) -> bool:
        """Navigate to the DM inbox."""
        try:
            self.logger.debug("Navigating to DM inbox...")
            
            # Way 1: tap the DM tab in the tab bar
            direct_tab = self.device.xpath(self.dm_selectors.direct_tab)
            if direct_tab.exists:
                direct_tab.click()
                time.sleep(2)
                self.logger.debug("✅ Navigated to DM inbox via direct_tab")
                return True
            
            # Méthode 2: Essayer via content-desc
            for selector in self.dm_selectors.direct_tab_content_desc:
                dm_btn = self.device.xpath(selector)
                if dm_btn.exists:
                    dm_btn.click()
                    time.sleep(2)
                    self.logger.debug("✅ Navigated to DM inbox via content-desc")
                    return True
            
            self.logger.error("DM tab not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to DM inbox: {e}")
            return False

    def _navigate_to_profile(self, username: str) -> bool:
        """Navigate to a user profile."""
        try:
            self.logger.debug(f"Navigating to profile: @{username}")
            
            # Use search to reach the profile
            # Tap the search tab
            for selector in self.nav_selectors.search_tab:
                search_tab = self.device.xpath(selector)
                if search_tab.exists:
                    search_tab.click()
                    time.sleep(2)
                    break
            else:
                self.logger.error("Search tab not found")
                return False
            
            # Tap the search bar
            search_field = self.device(**self.dm_selectors.message_input_class_selector)
            if search_field.exists(timeout=5):
                search_field.click()
                time.sleep(1)
                # SEARCH field, not the composer: typed straight, with no typo, because a
                # momentarily wrong letter reorders the suggestion list under the finger.
                # The device_id is resolved from the device itself, never guessed.
                device_id = dm_composer.resolve_device_id(
                    self.device, getattr(self.device_manager, 'device_id', None)
                )
                if not type_with_taktik_keyboard(device_id, username):
                    self.logger.warning("Taktik Keyboard failed, falling back to set_text")
                    search_field.set_text(username)
                time.sleep(2)
            else:
                self.logger.error("Search field not found")
                return False
            
            # Tap the first result (the account)
            # Find the account among the results
            account_result = self.device(
                **self.dm_selectors.account_result_selector_for_username(username)
            )
            if account_result.exists(timeout=5):
                account_result.click()
                time.sleep(2)
                self.logger.debug(f"✅ Navigated to @{username}")
                return True
            
            self.logger.error(f"Profile @{username} not found in search results")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to profile: {e}")
            return False

    def _follow_user(self) -> bool:
        """Follow the user when not already followed."""
        try:
            for selector in self.profile_selectors.follow_button:
                follow_btn = self.device.xpath(selector)
                if follow_btn.exists:
                    follow_btn.click()
                    time.sleep(1)
                    self.logger.debug("✅ User followed")
                    return True
            
            self.logger.debug("Follow button not found (might already be following)")
            return False
            
        except Exception as e:
            self.logger.error(f"Error following user: {e}")
            return False

    def _has_existing_conversation(self) -> bool:
        """Does a conversation already exist?"""
        # Could be improved by checking the DM history; for now this always
        # returns False (no check).
        return False

    def _open_dm_conversation(self) -> bool:
        """Open the DM conversation from the profile."""
        try:
            self.logger.debug("Opening DM conversation...")
            
            # Find the Message button on the profile
            for selector in self.profile_selectors.message_button:
                message_btn = self.device.xpath(selector)
                if message_btn.exists:
                    message_btn.click()
                    time.sleep(2)
                    self.logger.debug("✅ DM conversation opened")
                    return True
            
            # Fallback: look it up by text
            for label in self.profile_selectors.message_button_text_labels:
                message_btn = self.device(text=label)
                if message_btn.exists(timeout=3):
                    message_btn.click()
                    time.sleep(2)
                    return True
            
            self.logger.error("Message button not found on profile")
            return False
            
        except Exception as e:
            self.logger.error(f"Error opening DM conversation: {e}")
            return False

    def _send_message(self, message: str) -> bool:
        """
        Send the message in the conversation.
        
        Args:
                message: text to send
            
        Returns:
                True when sent successfully
        """
        try:
            self.logger.debug(f"Sending message ({len(message)} chars)...")

            # Locate, type and send through the shared composer primitive. The device_id
            # is resolved from the device itself, never defaulted.
            sent = dm_composer.send_message(
                self.device,
                getattr(self.device_manager, 'device_id', None),
                message,
                settle=1.0,
                logger=self.logger,
            )
            if sent:
                self.logger.debug("✅ Message sent")
            return sent

        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            return False

    def _go_back_to_home(self):
        """Go back to the home screen."""
        try:
            # Press back a few times
            for _ in range(3):
                self.device.press("back")
                time.sleep(0.5)
            
            # Tap the Home tab
            for selector in self.nav_selectors.home_tab:
                home_tab = self.device.xpath(selector)
                if home_tab.exists:
                    home_tab.click()
                    break
                    
        except Exception as e:
            self.logger.warning(f"Error going back to home: {e}")
