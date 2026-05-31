"""Navigation helpers for the Instagram Cold DM bridge."""

from __future__ import annotations

import time

from bridges.instagram.runtime.ipc import logger


class ColdDMNavigationMixin:
    """Search/profile navigation used by the Cold DM outreach flow."""

    def navigate_to_search(self) -> bool:
        """Navigate to the search/explore tab."""
        logger.info("Navigating to search...")

        search_btn = self.device(resourceId="com.instagram.android:id/search_tab")
        if search_btn.exists:
            search_btn.click()
            time.sleep(2)
            return True

        search_btn = self.device(description="Search and explore")
        if search_btn.exists:
            search_btn.click()
            time.sleep(2)
            return True

        search_btn = self.device(descriptionContains="Search")
        if search_btn.exists:
            search_btn.click()
            time.sleep(2)
            return True

        logger.error("Could not find search button")
        return False

    def search_user(self, username: str) -> bool:
        """Search for a user by username."""
        logger.info(f"Searching for user: {username}")
        username_lower = username.lower().strip()

        search_bar = self.device(resourceId="com.instagram.android:id/action_bar_search_edit_text")
        if not search_bar.exists:
            search_bar = self.device(text="Search")
        if not search_bar.exists:
            search_bar = self.device(className="android.widget.EditText")

        if not search_bar.exists:
            logger.error("Search bar not found")
            return False

        search_bar.click()
        time.sleep(0.5)
        search_bar.set_text(username)
        time.sleep(2)

        accounts_tab = self.device(text="Accounts")
        if accounts_tab.exists:
            logger.info("Clicking Accounts tab")
            accounts_tab.click()
            time.sleep(1.5)

        user_containers = self.device(resourceId="com.instagram.android:id/row_search_user_container")
        if user_containers.exists:
            logger.info(f"Found {user_containers.count} user containers")
            for i in range(min(user_containers.count, 10)):
                try:
                    container = user_containers[i]
                    username_elem = container.child(resourceId="com.instagram.android:id/row_search_user_username")
                    if username_elem.exists:
                        found_username = username_elem.get_text()
                        if found_username:
                            found_lower = found_username.lower().strip()
                            logger.info(f"Checking user {i}: '{found_username}'")
                            if found_lower == username_lower or username_lower in found_lower or found_lower in username_lower:
                                logger.info(f"Found matching user: {found_username}, clicking container")
                                container.click()
                                time.sleep(2)
                                return True
                except Exception as e:
                    logger.warning(f"Error checking container {i}: {e}")
                    continue

        first_username = self.device(resourceId="com.instagram.android:id/row_search_user_username")
        if first_username.exists:
            first_text = first_username.get_text()
            if first_text and username_lower in first_text.lower():
                logger.info(f"Clicking first matching result: {first_text}")
                first_username.click()
                time.sleep(2)
                return True

        logger.error(f"User {username} not found in search results")
        return False

    def is_private_profile(self) -> bool:
        """Check if the current profile is private."""
        private_state = self.device(resourceId="com.instagram.android:id/private_profile_empty_state")
        if private_state.exists:
            logger.info("Detected private profile (empty state)")
            return True

        private_text = self.device(textContains="account is private")
        if private_text.exists:
            logger.info("Detected private profile (text)")
            return True

        private_text_fr = self.device(textContains="compte est privé")
        if private_text_fr.exists:
            logger.info("Detected private profile (text FR)")
            return True

        return False

    def open_dm_from_profile(self):
        """Open DM conversation from a user's profile."""
        logger.info("Opening DM from profile...")

        if self.is_private_profile():
            logger.warning("Cannot send DM - profile is private")
            return "private"

        msg_btn = self.device(text="Message")
        if not msg_btn.exists:
            msg_btn = self.device(description="Message")
        if not msg_btn.exists:
            msg_btn = self.device(resourceId="com.instagram.android:id/profile_header_message_button")

        if msg_btn.exists:
            msg_btn.click()
            time.sleep(2)
            return True

        logger.error("Message button not found on profile")
        return False

    def go_back(self):
        """Go back to previous screen."""
        back_btn = self.device(resourceId="com.instagram.android:id/action_bar_button_back")
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

        home_btn = self.device(resourceId="com.instagram.android:id/feed_tab")
        if home_btn.exists:
            home_btn.click()
            time.sleep(2)
            return True

        home_btn = self.device(description="Home")
        if not home_btn.exists:
            home_btn = self.device(descriptionContains="Home")
        if home_btn.exists:
            home_btn.click()
            time.sleep(2)
            return True

        self.device.press("back")
        time.sleep(1)

        home_btn = self.device(resourceId="com.instagram.android:id/feed_tab")
        if home_btn.exists:
            home_btn.click()
            time.sleep(2)
            return True

        for _ in range(2):
            self.device.press("back")
            time.sleep(0.5)
        time.sleep(1)
        return True
