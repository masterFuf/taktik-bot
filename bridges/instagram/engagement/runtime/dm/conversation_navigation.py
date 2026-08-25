"""DM conversation lookup/opening helpers for the Instagram DM bridge."""

from __future__ import annotations

import time

from bridges.instagram.engagement.runtime.dm.conversation_payload import extract_inbox_username
from bridges.instagram.runtime.ipc import logger
from taktik.core.shared.behavior.gesture_primitives import human_scroll_raw
from taktik.core.shared.behavior.tap import tap_element_human
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
                            if not tap_element_human(self.device, item, logger=logger):
                                item.click()
                            time.sleep(2)
                            return True
            except Exception:
                continue
        return False

    def _search_conversation_by_digest(self, username_lower: str) -> bool:
        """Find a row through the version-patched ``thread_container`` xpath.

        The two native-id strategies above read ``row_inbox_container`` /
        ``row_inbox_username``, which Instagram v442 removed when it rebuilt the
        inbox rows in Compose. The xpath selector is the one the version-override
        framework patches per app version, and the row's content-desc still opens
        with the username — the same digest the reader parses. On the baseline
        version this finds the same rows the native ids do, so it is a safe
        third strategy rather than a v442-only branch.
        """
        try:
            threads = self.device.xpath(DM_SELECTORS.thread_container).all()
        except Exception:
            return False
        for thread in threads:
            try:
                content_desc = thread.info.get("contentDescription", "") or ""
                row_username = (extract_inbox_username(content_desc) or "").lower().strip()
                if not row_username:
                    continue
                if (
                    row_username == username_lower
                    or username_lower in row_username
                    or row_username in username_lower
                ):
                    logger.info(f"Found conversation via digest xpath: {row_username}")
                    if not tap_element_human(self.device, thread, logger=logger):
                        thread.click()
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
                        if not tap_element_human(self.device, elem, logger=logger):
                            elem.click()
                        time.sleep(2)
                        return True
            except Exception:
                continue

        if self._search_conversation_by_digest(username_lower):
            return True

        user_elem = self.device(textContains=username)
        if user_elem.exists:
            logger.info(f"Found via textContains: {username}")
            if not tap_element_human(self.device, user_elem, logger=logger):
                user_elem.click()
            time.sleep(2)
            return True

        for scroll_attempt in range(5):
            logger.info(f"Scrolling down to find conversation (attempt {scroll_attempt + 1}/5)...")
            human_scroll_raw(self.device, "down", logger=logger)
            time.sleep(1)

            if self._search_conversation_in_visible_list(username_lower):
                return True
            if self._search_conversation_by_digest(username_lower):
                return True

        logger.error(f"Conversation with {username} not found after scrolling")
        return False
