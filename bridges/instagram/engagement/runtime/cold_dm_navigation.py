"""Navigation helpers for the Instagram Cold DM bridge."""

from __future__ import annotations

import time

from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS


class ColdDMNavigationMixin:
    """Profile and home navigation used by the Cold DM outreach flow."""

    def is_private_profile(self) -> bool:
        """Check if the current profile is private."""
        private_state = self.device(resourceId=PROFILE_SELECTORS.private_empty_state_resource_id)
        if private_state.exists:
            logger.info("Detected private profile (empty state)")
            return True

        for text in PROFILE_SELECTORS.private_text_contains:
            private_text = self.device(textContains=text)
            if private_text.exists:
                logger.info("Detected private profile (text)")
                return True

        return False

    def open_dm_from_profile(self):
        """Open DM conversation from a user's profile."""
        logger.info("Opening DM from profile...")

        if self.is_private_profile():
            logger.warning("Cannot send DM - profile is private")
            return "private"

        msg_btn = None
        for label in PROFILE_SELECTORS.message_button_text_labels:
            msg_btn = self.device(text=label)
            if msg_btn.exists:
                break
            msg_btn = self.device(description=label)
            if msg_btn.exists:
                break
        if not msg_btn or not msg_btn.exists:
            msg_btn = self.device(resourceId=PROFILE_SELECTORS.message_button_resource_id)

        if msg_btn.exists:
            msg_btn.click()
            time.sleep(2)
            return True

        logger.error("Message button not found on profile")
        return False

    def go_back(self):
        """Go back to previous screen."""
        back_btn = self.device(resourceId=NAVIGATION_SELECTORS.action_bar_back_button_resource_id)
        if back_btn.exists:
            back_btn.click()
        else:
            self.device.press("back")
        time.sleep(1)

    def go_home(self):
        """Navigate to Instagram home screen."""
        logger.info("Navigating to home...")

        self.device.press("back")
        time.sleep(1)

        home_btn = self.device(resourceId=NAVIGATION_SELECTORS.home_tab_resource_id)
        if home_btn.exists:
            home_btn.click()
            time.sleep(2)
            return True

        for description in NAVIGATION_SELECTORS.home_tab_descriptions:
            home_btn = self.device(description=description)
            if home_btn.exists:
                home_btn.click()
                time.sleep(2)
                return True

        for description in NAVIGATION_SELECTORS.home_tab_description_contains:
            home_btn = self.device(descriptionContains=description)
            if home_btn.exists:
                home_btn.click()
                time.sleep(2)
                return True

        self.device.press("back")
        time.sleep(1)

        home_btn = self.device(resourceId=NAVIGATION_SELECTORS.home_tab_resource_id)
        if home_btn.exists:
            home_btn.click()
            time.sleep(2)
            return True

        for _ in range(2):
            self.device.press("back")
            time.sleep(0.5)
        time.sleep(1)
        return True
