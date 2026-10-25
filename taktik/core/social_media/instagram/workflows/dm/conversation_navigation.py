"""DM conversation lookup/opening helpers for the Instagram DM inbox."""

from __future__ import annotations

import time
from typing import Any, Optional

from taktik.core.social_media.instagram.workflows.dm.conversation_payload import (
    extract_inbox_username,
    same_inbox_name,
)
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

    device: Any  # the runtime's uiautomator2 device, behind the clone-aware proxy

    def _search_conversation_in_visible_list(self, username: str) -> Optional[bool]:
        """The row of `username` in the visible inbox list, opened (`_open_row`); None when
        no row shows that name."""
        inbox_items = self.device(resourceId=DM_SELECTORS.thread_container_resource_id)

        for i in range(min(inbox_items.count, 20)):
            try:
                item = inbox_items[i]
                username_elem = item.child(resourceId=DM_SELECTORS.thread_username_resource_id)
                item_username = username_elem.get_text() if username_elem.exists else None
            except Exception as exc:
                logger.debug(f"Inbox row {i} unreadable: {exc}")
                continue
            if same_inbox_name(item_username, username):
                logger.info(f"Found conversation: {item_username}")
                return self._open_row(item, username)
        return None

    def _search_conversation_by_username_rows(self, username: str) -> Optional[bool]:
        """The same, on the rows' username texts alone; None when none shows that name."""
        username_elems = self.device(resourceId=DM_SELECTORS.thread_username_resource_id)
        for i in range(min(username_elems.count, 20)):
            try:
                elem = username_elems[i]
                item_username = elem.get_text()
            except Exception as exc:
                logger.debug(f"Inbox row name {i} unreadable: {exc}")
                continue
            if same_inbox_name(item_username, username):
                logger.info(f"Found via direct username element: {item_username}")
                return self._open_row(elem, username)
        return None

    def _search_conversation_by_digest(self, username: str) -> Optional[bool]:
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
                row_username = extract_inbox_username(thread.info.get("contentDescription", "") or "")
            except Exception as exc:
                logger.debug(f"Inbox row digest unreadable: {exc}")
                continue
            if same_inbox_name(row_username, username):
                logger.info(f"Found conversation via digest xpath: {row_username}")
                return self._open_row(thread, username)
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
        """Open the conversation of `username` from the DM inbox on screen: the row of exactly that
        name (`same_inbox_name`), tapped, then the conversation on screen. False, nothing tapped, off
        the inbox, or when no row shows that name.

        A row whose name only holds the name asked for, or starts like it, is another account's:
        « bob » opened « bobby », and the reply that followed went into bobby's conversation.

        Only the inbox's rows are read, never a text anywhere on screen: a `textContains` match
        tapped the search field holding the handle, on the search results, and answered True
        (Pixel 6a, 447, 2026-10-25, the Lab's `dm.open_thread`)."""
        logger.info(f"Opening conversation with: {username}")
        if not dm_inbox_shown(self.device):
            logger.warning(f"The DM inbox is not on screen: no conversation with {username} looked for")
            return False

        # A row found is tapped once, and what it opened is the answer: nothing else is tapped.
        for find in (self._search_conversation_in_visible_list,
                     self._search_conversation_by_username_rows,
                     self._search_conversation_by_digest):
            opened = find(username)
            if opened is not None:
                return opened

        for scroll_attempt in range(5):
            logger.info(f"Scrolling down to find conversation (attempt {scroll_attempt + 1}/5)...")
            human_scroll_raw(self.device, "down", logger=logger)
            time.sleep(1)

            for find in (self._search_conversation_in_visible_list, self._search_conversation_by_digest):
                opened = find(username)
                if opened is not None:
                    return opened

        logger.error(f"Conversation with {username} not found after scrolling")
        return False
