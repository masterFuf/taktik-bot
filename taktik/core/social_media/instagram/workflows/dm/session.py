"""DM inbox session positioning helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass

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


@dataclass(frozen=True)
class DmListNotRead:
    """A list of conversations (the inbox, or its requests folder) the reader could not read: never
    an empty one. `error_code` names the cause in the catalogue of the bridges' codes
    (`contract/error_codes.py`), `error` says it for a person. (In TypeScript: the failure branch of
    a `{ ok: false, code, message }` union, the success branch being the list read.)"""

    error_code: str
    error: str


#: Neither the inbox nor its requests folder is on screen.
DM_INBOX_NOT_SHOWN = "DM_INBOX_NOT_SHOWN"
#: The list is on screen without a row, without its header and without its empty page: it has not loaded.
DM_LIST_NOT_LOADED = "DM_LIST_NOT_LOADED"
#: Instagram says the list did not load (its page offers to try again).
DM_LIST_LOAD_FAILED = "DM_LIST_LOAD_FAILED"

#: How long a list without rows may take to show them, its header or its empty page.
LIST_LOAD_TIMEOUT_S = 6.0


def dm_list_without_rows(device) -> DmListNotRead | None:
    """The verdict on a list that shows no row: None when the screen proves it empty, else why it is
    not read. The one rule (2026-10-25): « 0 conversation » only with the list's
    header or its empty page on screen; the action bar and the bare thread list are up before them.

    Waits up to `LIST_LOAD_TIMEOUT_S` for the header, the empty page, a row or the page of a failed
    load: the caller looks for its rows again after it. A page that failed to load is checked first:
    it shows a headline like the empty page."""
    wait_for_any(device, [DM_SELECTORS.thread_container, DM_SELECTORS.list_load_failed_link,
                          *DM_SELECTORS.list_loaded_markers], timeout=LIST_LOAD_TIMEOUT_S, label="dm-list")
    if find_element(device, [DM_SELECTORS.list_load_failed_link]) is not None:
        return DmListNotRead(error_code=DM_LIST_LOAD_FAILED,
                             error="Instagram did not load the conversations (its page offers to try again): "
                                   "nothing read")
    if find_element(device, DM_SELECTORS.list_loaded_markers) is not None:
        return None
    if not dm_inbox_shown(device):
        return inbox_not_shown()
    return DmListNotRead(error_code=DM_LIST_NOT_LOADED,
                         error="The conversations did not load (no row, no header, no empty page): nothing read")


def inbox_not_shown() -> DmListNotRead:
    """Why a reading on a screen that is not the inbox (nor its requests folder) reads nothing."""
    return DmListNotRead(error_code=DM_INBOX_NOT_SHOWN, error="The DM inbox is not on screen: no conversation read")


#: How long a conversation may take to come up after the tap that opens it.
CONVERSATION_OPEN_TIMEOUT_S = 6.0


def dm_conversation_shown(device, timeout: float = 0.0) -> bool:
    """Is a conversation open on screen? Its header bar (`conversation_screen_marker`), the one
    sign of a conversation, asked after every tap meant to open one: a tap only says that
    something was touched (Pixel 6a, 447, 2026-10-25: « open=True » on the search results).

    `timeout` > 0 waits that long for it: a conversation takes a second or two to come up.
    """
    marker = [DM_SELECTORS.conversation_screen_marker]
    if timeout <= 0:
        return find_element(device, marker) is not None
    return wait_for_any(device, marker, timeout=timeout, label="dm-conversation") is not None


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
