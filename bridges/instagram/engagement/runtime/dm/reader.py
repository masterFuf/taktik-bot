"""DM conversation reading and message extraction for the Instagram DM bridge."""

from __future__ import annotations

import json
import time

from bridges.instagram.engagement.runtime.dm.conversation_state import DMConversationStateMixin
from bridges.instagram.engagement.runtime.dm.message_extraction import DMMessageExtractionMixin
from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


class DMConversationReaderMixin(DMConversationStateMixin, DMMessageExtractionMixin):
    """Read DM conversations and extract visible message history."""

    def read_conversations(self, limit: int) -> list:
        """Read DM conversations."""
        conversations = []
        processed_usernames = set()
        processed_real_usernames = set()
        conversations_read = 0
        scroll_count = 0
        max_scrolls = 10

        while conversations_read < limit and scroll_count < max_scrolls:
            threads = self.device.xpath(DM_SELECTORS.thread_container).all()

            if not threads:
                logger.warning("No threads found")
                break

            threads_with_pos = []
            for thread in threads:
                try:
                    bounds = thread.info.get("bounds", {})
                    top = bounds.get("top", 0)
                    threads_with_pos.append((top, thread))
                except Exception:
                    continue
            threads_with_pos.sort(key=lambda x: x[0])

            new_conversations_in_scroll = 0

            for thread_top, thread in threads_with_pos:
                if conversations_read >= limit:
                    break

                try:
                    thread_info = thread.info
                    content_desc = thread_info.get("contentDescription", "")
                    username = _extract_inbox_username(content_desc)
                    username = self._resolve_thread_username(thread_info, username)

                    username_lower = username.lower().strip()
                    username_base = username_lower.rstrip(".").strip()
                    if _is_already_processed(username_base, processed_usernames):
                        logger.debug(f"Skipping already processed: {username}")
                        continue

                    logger.info(f"Opening conversation: {username}")
                    thread.click()
                    time.sleep(2)

                    header_title = self.device(resourceId=DM_SELECTORS.conversation_header_title_resource_id)
                    if not header_title.exists(timeout=3):
                        logger.warning(f"Could not open conversation with {username}")
                        self._return_to_inbox_if_needed()
                        continue

                    real_username = header_title.get_text() or username
                    real_username_lower = real_username.lower().strip()
                    if real_username_lower in processed_real_usernames:
                        logger.info(f"Skipping duplicate (real_username already seen): {real_username}")
                        self._go_back_from_conversation()
                        continue

                    processed_usernames.add(username_lower)
                    processed_real_usernames.add(real_username_lower)

                    is_group, can_reply = self._detect_conversation_reply_state(real_username)
                    messages = self._collect_messages()

                    last_message_is_ours = False
                    if messages:
                        last_msg = messages[-1]
                        if last_msg.get("is_sent", False):
                            last_message_is_ours = True
                            logger.info(f"Dernier message de @{real_username} est de NOUS -> can_reply=False")

                    if last_message_is_ours:
                        can_reply = False

                    conv = {
                        "username": real_username,
                        "inbox_username": username,
                        "messages": messages,
                        "is_group": is_group,
                        "can_reply": can_reply,
                        "last_message_is_ours": last_message_is_ours,
                    }
                    conversations.append(conv)
                    conversations_read += 1
                    new_conversations_in_scroll += 1

                    print(json.dumps({
                        "type": "conversation",
                        "current": conversations_read,
                        "total": limit,
                        "conversation": conv,
                    }), flush=True)

                    self._go_back_from_conversation(delay=1.5)

                except Exception as e:
                    logger.error(f"Error reading conversation: {e}")
                    self._return_to_inbox_if_needed()
                    continue

            if conversations_read >= limit:
                break

            if self._is_accounts_to_follow_visible():
                logger.info("Reached bottom of DM inbox (Accounts to follow visible), stopping read")
                break

            if new_conversations_in_scroll == 0:
                logger.info("No new conversations found in current inbox viewport, stopping read")
                break

            scroll_count += 1
            self.device.swipe(
                self.screen_width // 2, int(self.screen_height * 0.7),
                self.screen_width // 2, int(self.screen_height * 0.3),
                duration=0.3,
            )
            time.sleep(1.5)

        return conversations


def _extract_inbox_username(content_desc: str) -> str:
    if content_desc:
        parts = content_desc.split(",")
        if parts:
            return parts[0].strip()
    return "Unknown"


def _is_already_processed(username_base: str, processed_usernames: set[str]) -> bool:
    for processed in processed_usernames:
        processed_base = processed.rstrip(".").strip()
        if (
            username_base == processed_base
            or username_base.startswith(processed_base)
            or processed_base.startswith(username_base)
        ):
            return True
    return False
