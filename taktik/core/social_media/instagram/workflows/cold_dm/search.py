"""Search navigation helpers for the Instagram Cold DM workflow."""

from __future__ import annotations

import time
from typing import Any

from loguru import logger
from taktik.core.shared.input.taktik_keyboard import ensure_taktik_keyboard, type_text_checked
from taktik.core.social_media.instagram.actions.atomic.text.dm_composer import resolve_device_id
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS


class ColdDMSearchMixin:
    """Search-tab navigation used by the Cold DM outreach flow.

    Reads the host's Taktik Keyboard service (`self._keyboard`, its `device_id`), set by
    `ColdDMSenderMixin._init_cold_dm_sender`.
    """

    # What the host gives this mixin, like the fields of a TypeScript interface.
    device: Any  # the (clone-aware) uiautomator2 device
    _keyboard: Any  # the host's Taktik Keyboard service

    def navigate_to_search(self) -> bool:
        """Navigate to the search/explore tab."""
        logger.info("Navigating to search...")

        search_btn = self.device(resourceId=NAVIGATION_SELECTORS.search_tab_resource_id)
        if search_btn.exists:
            search_btn.click()
            time.sleep(2)
            return True

        for description in NAVIGATION_SELECTORS.search_tab_descriptions:
            search_btn = self.device(description=description)
            if search_btn.exists:
                search_btn.click()
                time.sleep(2)
                return True

        for description in NAVIGATION_SELECTORS.search_tab_description_contains:
            search_btn = self.device(descriptionContains=description)
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

        search_bar = self.device(resourceId=NAVIGATION_SELECTORS.explore_search_bar_resource_id)
        for text in NAVIGATION_SELECTORS.explore_search_bar_texts:
            if search_bar.exists:
                break
            search_bar = self.device(text=text)
        if not search_bar.exists:
            search_bar = self.device(className=NAVIGATION_SELECTORS.edit_text_class_name)

        if not search_bar.exists:
            logger.error("Search bar not found")
            return False

        # Typed through the Taktik Keyboard, switched before the tap (a switch after it can cost
        # the field its focus). It was written with `set_text`: the whole handle at once, no key
        # pressed. A keyboard that does not type is a failed search, nothing pasted.
        device_id = resolve_device_id(self.device, self._keyboard.device_id)
        ensure_taktik_keyboard(device_id)
        search_bar.click()
        time.sleep(0.5)
        if not type_text_checked(self.device, device_id, username, typos=False):
            logger.error(f"The Taktik Keyboard did not type @{username} in the search bar: "
                         "not searched, nothing pasted")
            return False
        time.sleep(2)

        for text in NAVIGATION_SELECTORS.search_accounts_tab_texts:
            accounts_tab = self.device(text=text)
            if accounts_tab.exists:
                logger.info("Clicking Accounts tab")
                accounts_tab.click()
                time.sleep(1.5)
                break

        user_containers = self.device(resourceId=NAVIGATION_SELECTORS.search_result_container_resource_id)
        if user_containers.exists:
            logger.info(f"Found {user_containers.count} user containers")
            for i in range(min(user_containers.count, 10)):
                try:
                    container = user_containers[i]
                    username_elem = container.child(resourceId=NAVIGATION_SELECTORS.search_result_username_resource_id)
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

        first_username = self.device(resourceId=NAVIGATION_SELECTORS.search_result_username_resource_id)
        if first_username.exists:
            first_text = first_username.get_text()
            if first_text and username_lower in first_text.lower():
                logger.info(f"Clicking first matching result: {first_text}")
                first_username.click()
                time.sleep(2)
                return True

        logger.error(f"User {username} not found in search results")
        return False
