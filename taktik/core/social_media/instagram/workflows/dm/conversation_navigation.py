"""DM conversation lookup/opening helpers for the Instagram DM inbox."""

from __future__ import annotations

import time
from typing import Optional

from taktik.core.social_media.instagram.workflows.dm.conversation_payload import extract_inbox_username
from loguru import logger
from taktik.core.shared.behavior.gesture_primitives import human_scroll_raw
from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from taktik.core.social_media.instagram.workflows.dm.session import (
    CONVERSATION_OPEN_TIMEOUT_S,
    dm_conversation_shown,
    dm_inbox_shown,
)


class DMConversationNavigationMixin:
    """Find and open a specific conversation from the DM inbox."""

    def _search_conversation_in_visible_list(self, username_lower: str) -> Optional[bool]:
        """The row of `username_lower` in the visible inbox list, opened (`_open_row`); None when
        no row shows that name."""
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
                            return self._open_row(item, item_username)
            except Exception:
                continue
        return None

    def _search_conversation_by_username_rows(self, username_lower: str) -> Optional[bool]:
        """The same, on the rows' username texts alone; None when none shows that name."""
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
                        return self._open_row(elem, item_username)
            except Exception:
                continue
        return None

    def _search_conversation_by_digest(self, username_lower: str) -> Optional[bool]:
        """Find a row through the version-patched ``thread_container`` xpath.

        The two native-id strategies above read ``row_inbox_container`` /
        ``row_inbox_username``, which Instagram v442 removed when it rebuilt the
        inbox rows in Compose. The xpath selector is the one the version-override
        framework patches per app version, and the row's content-desc still opens
        with the username — the same digest the reader parses. On the baseline
        version this finds the same rows the native ids do, so it is a safe
        third strategy rather than a v442-only branch. None when no row shows that name.
        """
        try:
            threads = self.device.xpath(DM_SELECTORS.thread_container).all()
        except Exception as exc:
            logger.warning(f"Inbox rows unreadable by their digest: {exc}")
            return None
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
                    return self._open_row(thread, row_username)
            except Exception:
                continue
        return None

    def _open_row(self, row, shown_name: str) -> bool:
        """Tap the inbox row of `shown_name`, then wait for its conversation
        (`dm_conversation_shown`): a tap only says that something was touched."""
        if not tap_element_human(self.device, row, logger=logger):
            row.click()
        if dm_conversation_shown(self.device, timeout=CONVERSATION_OPEN_TIMEOUT_S):
            return True
        logger.warning(f"The row of {shown_name} was tapped, but no conversation came up")
        return False

    def open_conversation(self, username: str) -> bool:
        """Open the conversation of `username` from the DM inbox on screen: its row, tapped, then
        the conversation on screen. False, nothing tapped, off the inbox.

        Only the inbox's rows are read, never a text anywhere on screen: a `textContains` match
        tapped the search field holding the handle, on the search results, and answered True
        (Pixel 6a, 447, 2026-10-25, the Lab's `dm.open_thread`)."""
        logger.info(f"Opening conversation with: {username}")
        if not dm_inbox_shown(self.device):
            logger.warning(f"The DM inbox is not on screen: no conversation with {username} looked for")
            return False
        username_lower = username.lower().strip()

        # A row found is tapped once, and what it opened is the answer: nothing else is tapped.
        for find in (self._search_conversation_in_visible_list,
                     self._search_conversation_by_username_rows,
                     self._search_conversation_by_digest):
            opened = find(username_lower)
            if opened is not None:
                return opened

        for scroll_attempt in range(5):
            logger.info(f"Scrolling down to find conversation (attempt {scroll_attempt + 1}/5)...")
            human_scroll_raw(self.device, "down", logger=logger)
            time.sleep(1)

            for find in (self._search_conversation_in_visible_list, self._search_conversation_by_digest):
                opened = find(username_lower)
                if opened is not None:
                    return opened

        logger.error(f"Conversation with {username} not found after scrolling")
        return False
