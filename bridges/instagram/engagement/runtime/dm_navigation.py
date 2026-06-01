"""DM inbox and conversation navigation for the Instagram DM bridge."""

from __future__ import annotations

import time

from bridges.instagram.engagement.runtime.dm_conversation_navigation import DMConversationNavigationMixin
from bridges.instagram.engagement.runtime.dm_inbox_reset import DMInboxResetMixin
from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


class DMInboxNavigationMixin(DMConversationNavigationMixin, DMInboxResetMixin):
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
