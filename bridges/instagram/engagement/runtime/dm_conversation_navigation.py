"""DM conversation lookup/opening helpers for the Instagram DM bridge."""

from __future__ import annotations

import time

from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


class DMConversationNavigationMixin:
    """Find and open a specific conversation from the DM inbox."""

    def _search_conversation_in_visible_list(self, username_lower: str) -> bool:
        """Search for a conversation in the currently visible inbox list."""
        inbox_items = self.device(resourceId=DM_SELECTORS.thread_container_resource_id)

        for i in range(min(inbox_items.count, 20)):
            try:
                item = inbox_items[i]
                username_elem = item.child(resourceId=DM_SELECTORS.thread_username_resource_id)
                if username_elem.exists:
                    item_username = username_elem.get_text()
                    if item_username:
                        item_username_lower = item_username.lower().strip()
                        if (
                            item_username_lower == username_lower
                            or username_lower in item_username_lower
                            or item_username_lower in username_lower
                        ):
                            logger.info(f"Found conversation: {item_username}")
                            item.click()
                            time.sleep(2)
                            return True
            except Exception:
                continue
        return False

    def open_conversation(self, username: str) -> bool:
        """Open a specific conversation by username."""
        logger.info(f"Opening conversation with: {username}")
        username_lower = username.lower().strip()

        if self._search_conversation_in_visible_list(username_lower):
            return True

        logger.info("Trying direct search on all row_inbox_username elements...")
        username_elems = self.device(resourceId=DM_SELECTORS.thread_username_resource_id)
        for i in range(min(username_elems.count, 20)):
            try:
                elem = username_elems[i]
                item_username = elem.get_text()
                if item_username:
                    item_username_lower = item_username.lower().strip()
                    if (
                        item_username_lower == username_lower
                        or username_lower in item_username_lower
                        or item_username_lower in username_lower
                    ):
                        logger.info(f"Found via direct username element: {item_username}")
                        elem.click()
                        time.sleep(2)
                        return True
            except Exception:
                continue

        user_elem = self.device(textContains=username)
        if user_elem.exists:
            logger.info(f"Found via textContains: {username}")
            user_elem.click()
            time.sleep(2)
            return True

        for scroll_attempt in range(5):
            logger.info(f"Scrolling down to find conversation (attempt {scroll_attempt + 1}/5)...")
            self.device.swipe(
                self.screen_width // 2,
                int(self.screen_height * 0.7),
                self.screen_width // 2,
                int(self.screen_height * 0.3),
                duration=0.3,
            )
            time.sleep(1)

            if self._search_conversation_in_visible_list(username_lower):
                return True

        logger.error(f"Conversation with {username} not found after scrolling")
        return False
