"""DM inbox and conversation navigation for the Instagram DM inbox."""

from __future__ import annotations

import time
from typing import Any

from taktik.core.social_media.instagram.workflows.dm.conversation_navigation import DMConversationNavigationMixin
from taktik.core.social_media.instagram.workflows.dm.inbox_reset import DMInboxResetMixin
from loguru import logger
from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.shared.device.wait import find_element, wait_for_any
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from taktik.core.social_media.instagram.workflows.dm.session import dm_inbox_shown

#: How long a tap on the DM entry waits for the inbox: more than the 5 s that missed it on a
#: Pixel 6 Pro (see `dm_inbox_shown`).
INBOX_ARRIVAL_TIMEOUT_S = 10.0


def open_dm_inbox(device) -> bool:
    """Open the DM inbox. True only once its conversation list is on screen.

    Several ways to find the DM entry, tried in order; the first entry found is tapped, and the
    answer is the arrival, never the tap. On a visited profile the "Message" button carries the
    same description as the inbox entry and opens a conversation with that account (Instagram
    410, Lab auto-test): a tap that does not reach the inbox is undone with Back and no other way
    is tried, each would find the same look-alike. The callers recover from the home screen.

    One opener for every DM path: the runtime's `navigate_to_dm_inbox`, and the conversation
    opener of a profile without a Message button (`MessagingBusiness`).
    """
    logger.info("Navigating to DM inbox...")

    logger.info("Trying method 1: direct_tab resource-id (uiautomator2)...")
    dm_tab = device(resourceId=DM_SELECTORS.direct_tab_resource_id)
    if dm_tab.exists:
        return _open_dm_inbox_through(device, dm_tab, "direct_tab (uiautomator2)")

    logger.info("Trying method 2: content-desc 'Message'...")
    for desc in DM_SELECTORS.dm_inbox_button_descriptions:
        btn = device(description=desc)
        if btn.exists:
            return _open_dm_inbox_through(device, btn, f"content-desc: {desc}")

    logger.info("Trying method 3: direct_tab xpath...")
    dm_tab = device.xpath(DM_SELECTORS.direct_tab)
    if dm_tab.exists:
        return _open_dm_inbox_through(device, dm_tab, "direct_tab xpath")

    logger.info("Trying method 4: DM_SELECTORS content-desc xpaths...")
    for selector in DM_SELECTORS.direct_tab_content_desc:
        dm_btn = device.xpath(selector)
        if dm_btn.exists:
            return _open_dm_inbox_through(device, dm_btn, f"content-desc xpath: {selector}")

    logger.info("Trying method 5: action_bar_inbox_button...")
    messenger = device(resourceId=DM_SELECTORS.action_bar_inbox_button_resource_id)
    if messenger.exists:
        return _open_dm_inbox_through(device, messenger, "messenger icon")

    logger.info("Trying method 6: descriptionContains variations...")
    for desc in DM_SELECTORS.dm_inbox_description_contains:
        btn = device(descriptionContains=desc)
        if btn.exists:
            return _open_dm_inbox_through(device, btn, f"descriptionContains: {desc}")

    logger.info("Trying method 7: ImageView in action bar...")
    action_bar = device(resourceId=DM_SELECTORS.inbox_action_bar_resource_id)
    if action_bar.exists:
        images = action_bar.child(className=DM_SELECTORS.image_view_class_name, clickable=True)
        if images.count > 0:
            return _open_dm_inbox_through(device, images[images.count - 1], "action bar ImageView")

    logger.error("Cannot find DM button - all methods failed")
    return False


def _open_dm_inbox_through(device, entry, how: str) -> bool:
    """Tap one DM entry; True once the inbox is up (waited for), else Back and False."""
    if not tap_element_human(device, entry, logger=logger):
        entry.click()
    if dm_inbox_shown(device, timeout=INBOX_ARRIVAL_TIMEOUT_S):
        logger.info(f"Navigated via {how}")
        return True
    logger.warning(f"Tapped the DM entry ({how}) but the DM inbox did not come up, pressing back")
    device.press("back")
    time.sleep(1)
    return False


class DMInboxNavigationMixin(DMConversationNavigationMixin, DMInboxResetMixin):
    """Navigation helpers shared by DM read/send commands."""

    device: Any  # the runtime's uiautomator2 device, behind the clone-aware proxy

    def navigate_to_dm_inbox(self) -> bool:
        """Open the DM inbox (`open_dm_inbox`). True only once it is on screen."""
        return open_dm_inbox(self.device)

    def open_requests_folder(self) -> bool:
        """From the DM inbox, open the message-requests folder (Requests/Demandes/Invitations).

        Instagram serves two inbox layouts on the same 410, per account: the requests entry is
        the header action button (resource-id ``header_action_button``) on one, a pill of the
        header (Tout / Principal / Général / Invitations) on the other (Pixel 6 Pro, 2026-10-24).
        Request rows reuse the same ``row_inbox_container`` structure as the primary inbox, so
        the existing read loop can read them once we are on this screen. Returns False when
        there is no requests entry (no pending requests) or the screen did not open.
        """
        logger.info("Opening message requests folder...")
        entries = [DM_SELECTORS.inbox_header_action_button] + DM_SELECTORS.requests_pill
        found = wait_for_any(self.device, entries, timeout=3, label="dm-requests-entry")
        if found is None:
            logger.info("No message-requests entry in the inbox header (no pending requests?)")
            return False
        entry = self.device.xpath(found)
        if not tap_element_human(self.device, entry, logger=logger):
            entry.click()
        time.sleep(2)
        # The thread-list recyclerview exists on BOTH the inbox and the requests screen, so
        # confirm via the action-bar title (e.g. "Message requests" / "Demandes" / "Invitations"),
        # or, on the pill layout, by the requests pill shown as the one on display.
        title = self.device(resourceId=DM_SELECTORS.action_bar_title_resource_id)
        title_text = (title.get_text() or "") if title.exists(timeout=3) else ""
        if any(fragment in title_text for fragment in DM_SELECTORS.requests_title_fragments):
            logger.info(f"Message requests folder opened (title: {title_text})")
            return True
        if find_element(self.device, DM_SELECTORS.requests_pill_selected) is not None:
            logger.info("Message requests shown (requests pill selected)")
            return True
        logger.warning(f"Tapped the requests entry but did not reach the requests screen (title: '{title_text}')")
        return False
