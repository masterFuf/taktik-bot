"""DM inbox and conversation navigation for the Instagram DM bridge."""

from __future__ import annotations

import time

from bridges.instagram.engagement.runtime.dm_inbox_reset import DMInboxResetMixin
from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


class DMInboxNavigationMixin(DMInboxResetMixin):
    """Navigation helpers shared by DM read/send commands."""

    def navigate_to_dm_inbox(self) -> bool:
        """Navigate to DM inbox using multiple methods."""
        logger.info("Navigating to DM inbox...")

        logger.info("Trying method 1: direct_tab resource-id (uiautomator2)...")
        dm_tab = self.device(resourceId=DM_SELECTORS.direct_tab_resource_id)
        if dm_tab.exists:
            dm_tab.click()
            time.sleep(2)
            logger.info("Navigated via direct_tab (uiautomator2)")
            return True

        logger.info("Trying method 2: content-desc 'Message'...")
        for desc in DM_SELECTORS.dm_inbox_button_descriptions:
            btn = self.device(description=desc)
            if btn.exists:
                btn.click()
                time.sleep(2)
                logger.info(f"Navigated via content-desc: {desc}")
                return True

        logger.info("Trying method 3: direct_tab xpath...")
        dm_tab = self.device.xpath(DM_SELECTORS.direct_tab)
        if dm_tab.exists:
            dm_tab.click()
            time.sleep(2)
            logger.info("Navigated via direct_tab xpath")
            return True

        logger.info("Trying method 4: DM_SELECTORS content-desc xpaths...")
        for selector in DM_SELECTORS.direct_tab_content_desc:
            dm_btn = self.device.xpath(selector)
            if dm_btn.exists:
                dm_btn.click()
                time.sleep(2)
                logger.info(f"Navigated via content-desc xpath: {selector}")
                return True

        logger.info("Trying method 5: action_bar_inbox_button...")
        messenger = self.device(resourceId=DM_SELECTORS.action_bar_inbox_button_resource_id)
        if messenger.exists:
            messenger.click()
            time.sleep(2)
            logger.info("Navigated via messenger icon")
            return True

        logger.info("Trying method 6: descriptionContains variations...")
        for desc in DM_SELECTORS.dm_inbox_description_contains:
            btn = self.device(descriptionContains=desc)
            if btn.exists:
                btn.click()
                time.sleep(2)
                inbox = self.device(resourceId=DM_SELECTORS.inbox_thread_list_resource_id)
                if inbox.exists:
                    logger.info(f"Navigated via descriptionContains: {desc}")
                    return True
                logger.warning(f"Clicked '{desc}' but did not reach DM inbox, pressing back")
                self.device.press("back")
                time.sleep(1)

        logger.info("Trying method 7: ImageView in action bar...")
        action_bar = self.device(resourceId=DM_SELECTORS.inbox_action_bar_resource_id)
        if action_bar.exists:
            images = action_bar.child(className=DM_SELECTORS.image_view_class_name, clickable=True)
            if images.count > 0:
                images[images.count - 1].click()
                time.sleep(2)
                inbox = self.device(resourceId=DM_SELECTORS.inbox_thread_list_resource_id)
                if inbox.exists:
                    logger.info("Navigated via action bar ImageView")
                    return True
                logger.warning("Clicked action bar ImageView but did not reach DM inbox, pressing back")
                self.device.press("back")
                time.sleep(1)

        logger.error("Cannot find DM button - all methods failed")
        return False

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
                self.screen_width // 2, int(self.screen_height * 0.7),
                self.screen_width // 2, int(self.screen_height * 0.3),
                duration=0.3,
            )
            time.sleep(1)

            if self._search_conversation_in_visible_list(username_lower):
                return True

        logger.error(f"Conversation with {username} not found after scrolling")
        return False
