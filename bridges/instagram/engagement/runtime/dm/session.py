"""DM bridge session positioning helpers."""

from __future__ import annotations

import time

from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


def ensure_dm_inbox(bridge) -> bool:
    """
    Ensure Instagram is open and we're in the DM inbox.
    Handles the case where the user left Instagram or navigated away.
    Returns True if we're in the inbox, False if navigation failed.
    """
    inbox = bridge.device(resourceId=DM_SELECTORS.inbox_thread_list_resource_id)
    if inbox.exists(timeout=2):
        logger.info("Already in DM inbox")
        bridge._ensure_primary_tab()
        return True

    ig_elements = [
        bridge.device(resourceId=resource_id)
        for resource_id in DM_SELECTORS.instagram_open_probe_resource_ids
    ]
    ig_is_open = any(e.exists(timeout=1) for e in ig_elements)

    if ig_is_open:
        logger.info("Instagram is open but not in DM inbox, navigating...")
        if bridge.navigate_to_dm_inbox():
            time.sleep(2)
            bridge._ensure_primary_tab()
            bridge._scroll_to_top_of_inbox()
            return True

    logger.info("Instagram not in DM inbox, restarting app...")
    bridge.restart_instagram()
    time.sleep(3)

    if not bridge.navigate_to_dm_inbox():
        logger.error("Failed to navigate to DM inbox after restart")
        return False

    time.sleep(2)
    bridge._ensure_primary_tab()
    bridge._scroll_to_top_of_inbox()
    return True


def return_to_inbox(bridge) -> None:
    """Return to the DM inbox from an opened conversation."""
    time.sleep(0.5)
    back_btn = bridge.device(resourceId=DM_SELECTORS.conversation_back_button_resource_id)
    if back_btn.exists(timeout=2):
        back_btn.click()
        logger.info("Retour a l'inbox via header_left_button")
        time.sleep(1)
        return

    for description in DM_SELECTORS.conversation_back_descriptions:
        back_btn = bridge.device(description=description)
        if back_btn.exists(timeout=2):
            back_btn.click()
            logger.info(f"Retour a l'inbox via description {description}")
            time.sleep(1)
            return

    logger.warning("Bouton back non trouve, tentative press back")
    bridge.device.press("back")
    time.sleep(1)
