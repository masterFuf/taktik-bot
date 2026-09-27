"""DM inbox and conversation navigation for the Instagram DM inbox."""

from __future__ import annotations

import time

from taktik.core.social_media.instagram.workflows.dm_inbox.conversation_navigation import DMConversationNavigationMixin
from taktik.core.social_media.instagram.workflows.dm_inbox.inbox_reset import DMInboxResetMixin
from loguru import logger
from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


class DMInboxNavigationMixin(DMConversationNavigationMixin, DMInboxResetMixin):
    """Navigation helpers shared by DM read/send commands."""

    def navigate_to_dm_inbox(self) -> bool:
        """Open the DM inbox. True only once its conversation list is on screen.

        Several ways to find the DM entry, tried in order; the first entry found is tapped, and the
        answer is the arrival, never the tap. On a visited profile the "Message" button carries the
        same description as the inbox entry and opens a conversation with that account (Instagram
        410, Lab auto-test): a tap that does not reach the inbox is undone with Back and no other way
        is tried, each would find the same look-alike. The callers recover from the home screen.
        """
        logger.info("Navigating to DM inbox...")

        logger.info("Trying method 1: direct_tab resource-id (uiautomator2)...")
        dm_tab = self.device(resourceId=DM_SELECTORS.direct_tab_resource_id)
        if dm_tab.exists:
            return self._open_dm_inbox_through(dm_tab, "direct_tab (uiautomator2)")

        logger.info("Trying method 2: content-desc 'Message'...")
        for desc in DM_SELECTORS.dm_inbox_button_descriptions:
            btn = self.device(description=desc)
            if btn.exists:
                return self._open_dm_inbox_through(btn, f"content-desc: {desc}")

        logger.info("Trying method 3: direct_tab xpath...")
        dm_tab = self.device.xpath(DM_SELECTORS.direct_tab)
        if dm_tab.exists:
            return self._open_dm_inbox_through(dm_tab, "direct_tab xpath")

        logger.info("Trying method 4: DM_SELECTORS content-desc xpaths...")
        for selector in DM_SELECTORS.direct_tab_content_desc:
            dm_btn = self.device.xpath(selector)
            if dm_btn.exists:
                return self._open_dm_inbox_through(dm_btn, f"content-desc xpath: {selector}")

        logger.info("Trying method 5: action_bar_inbox_button...")
        messenger = self.device(resourceId=DM_SELECTORS.action_bar_inbox_button_resource_id)
        if messenger.exists:
            return self._open_dm_inbox_through(messenger, "messenger icon")

        logger.info("Trying method 6: descriptionContains variations...")
        for desc in DM_SELECTORS.dm_inbox_description_contains:
            btn = self.device(descriptionContains=desc)
            if btn.exists:
                return self._open_dm_inbox_through(btn, f"descriptionContains: {desc}")

        logger.info("Trying method 7: ImageView in action bar...")
        action_bar = self.device(resourceId=DM_SELECTORS.inbox_action_bar_resource_id)
        if action_bar.exists:
            images = action_bar.child(className=DM_SELECTORS.image_view_class_name, clickable=True)
            if images.count > 0:
                return self._open_dm_inbox_through(images[images.count - 1], "action bar ImageView")

        logger.error("Cannot find DM button - all methods failed")
        return False

    def _open_dm_inbox_through(self, entry, how: str) -> bool:
        """Tap one DM entry; True once the inbox's conversation list is up, else Back and False."""
        if not tap_element_human(self.device, entry, logger=logger):
            entry.click()
        time.sleep(2)
        if self.device(resourceId=DM_SELECTORS.inbox_thread_list_resource_id).exists(timeout=3):
            logger.info(f"Navigated via {how}")
            return True
        logger.warning(f"Tapped the DM entry ({how}) but the DM inbox did not come up, pressing back")
        self.device.press("back")
        time.sleep(1)
        return False

    def open_requests_folder(self) -> bool:
        """From the DM inbox, open the message-requests folder (Requests/Demandes/Invitations).

        The entry is the inbox header action button (resource-id ``header_action_button``).
        Request rows reuse the same ``row_inbox_container`` structure as the primary inbox, so
        the existing read loop can read them once we are on this screen. Returns False when
        there is no requests entry (no pending requests) or the screen did not open.
        """
        logger.info("Opening message requests folder...")
        button = self.device(resourceId=DM_SELECTORS.inbox_header_action_button_resource_id)
        if not button.exists(timeout=3):
            logger.info("No message-requests entry in the inbox header (no pending requests?)")
            return False
        if not tap_element_human(self.device, button, logger=logger):
            button.click()
        time.sleep(2)
        # The thread-list recyclerview exists on BOTH the inbox and the requests screen, so
        # confirm via the action-bar title (e.g. "Message requests" / "Demandes" / "Invitations").
        title = self.device(resourceId=DM_SELECTORS.action_bar_title_resource_id)
        title_text = (title.get_text() or "") if title.exists(timeout=3) else ""
        if any(fragment in title_text for fragment in DM_SELECTORS.requests_title_fragments):
            logger.info(f"Message requests folder opened (title: {title_text})")
            return True
        logger.warning(f"Tapped the requests entry but did not reach the requests screen (title: '{title_text}')")
        return False
