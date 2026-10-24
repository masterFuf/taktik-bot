"""DM inbox session positioning helpers."""

from __future__ import annotations

import time

from loguru import logger
from taktik.core.shared.device.wait import find_element, wait_for_any
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


def dm_inbox_shown(device, timeout: float = 0.0) -> bool:
    """Is the DM inbox on screen? The one recognition every DM path asks.

    Read in the screen's dump, as the inbox reader reads its rows, on any of the markers only
    the inbox shows. `timeout` > 0 waits that long for one of them: right after a tap on the DM
    entry the inbox can take seconds to come up (Pixel 6 Pro, Android 17, Instagram 410,
    2026-10-24: not there when the opener looked 5 s after its tap, on screen in the capture
    taken about 2 s later).
    """
    markers = DM_SELECTORS.inbox_screen_markers
    if timeout <= 0:
        return find_element(device, markers) is not None
    return wait_for_any(device, markers, timeout=timeout, label="dm-inbox") is not None


def ensure_dm_inbox(bridge) -> bool:
    """
    Ensure Instagram is open and we're in the DM inbox.
    Handles the case where the user left Instagram or navigated away.
    Returns True if we're in the inbox, False if navigation failed.
    """
    if dm_inbox_shown(bridge.device, timeout=2):
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
