"""DM conversation reading and message extraction for the Instagram DM bridge."""

from __future__ import annotations

import json
import re
import time

from bridges.instagram.base import logger
from taktik.core.social_media.instagram.ui.selectors import DM_SELECTORS


class DMConversationReaderMixin:
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

                    header_title = self.device(resourceId="com.instagram.android:id/header_title")
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

    def _resolve_thread_username(self, thread_info: dict, fallback: str) -> str:
        username = fallback
        try:
            username_elem = self.device(resourceId="com.instagram.android:id/row_inbox_username")
            if username_elem.exists:
                for idx in range(username_elem.count):
                    elem = username_elem[idx]
                    bounds = elem.info.get("bounds", {})
                    thread_bounds = thread_info.get("bounds", {})
                    if bounds and thread_bounds:
                        if (
                            bounds.get("top", 0) >= thread_bounds.get("top", 0)
                            and bounds.get("bottom", 0) <= thread_bounds.get("bottom", 0)
                        ):
                            username = elem.get_text() or username
                            break
        except Exception:
            pass
        return username

    def _detect_conversation_reply_state(self, real_username: str) -> tuple[bool, bool]:
        is_group = False
        can_reply = True
        header_subtitle = self.device(resourceId="com.instagram.android:id/header_subtitle")
        if header_subtitle.exists:
            try:
                subtitle_text = header_subtitle.get_text() or ""
                subtitle_info = header_subtitle.info
                subtitle_desc = subtitle_info.get("contentDescription", "") or ""
                combined = (subtitle_text + " " + subtitle_desc).lower()
                is_group_pattern = bool(re.search(r"\d+\.?\d*k?\s*(membres|members)", combined))

                if is_group_pattern or "membres" in combined or "members" in combined:
                    is_group = True
                    logger.info(f"Groupe détecté via subtitle: {combined[:50]}")
            except Exception as e:
                logger.debug(f"Erreur détection groupe via subtitle: {e}")

        composer = self.device(resourceId="com.instagram.android:id/row_thread_composer_edittext")
        if not composer.exists:
            can_reply = False
            if not is_group:
                is_group = True
                logger.info(f"Broadcast channel détecté (pas de composer): {real_username}")

        return is_group, can_reply

    def _return_to_inbox_if_needed(self) -> None:
        inbox_list = self.device(resourceId="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview")
        if not inbox_list.exists:
            self._go_back_from_conversation(delay=1)

    def _go_back_from_conversation(self, delay: float = 1) -> None:
        back_btn = self.device(resourceId="com.instagram.android:id/header_left_button")
        if back_btn.exists:
            back_btn.click()
        else:
            self.device.press("back")
        time.sleep(delay)

    def _collect_messages(self) -> list:
        """Collect messages from current conversation."""
        all_items = []
        all_items.extend(self._collect_text_messages())
        all_items.extend(self._collect_reel_messages())
        all_items.sort(key=lambda x: x["top"])

        return [
            {
                "type": msg["type"],
                "text": msg["text"],
                "is_sent": msg["is_sent"],
            }
            for msg in all_items
        ]

    def _collect_text_messages(self) -> list[dict]:
        items = []
        msg_elements = self.device(resourceId="com.instagram.android:id/direct_text_message_text_view")
        for j in range(msg_elements.count):
            try:
                msg_elem = msg_elements[j]
                msg_bounds = msg_elem.info.get("bounds", {})
                text = msg_elem.get_text()
                if not text:
                    continue
                msg_left = msg_bounds.get("left", 0)
                msg_top = msg_bounds.get("top", 0)
                is_received = msg_left < self.screen_width * 0.25
                items.append({
                    "type": "text",
                    "text": text,
                    "is_sent": not is_received,
                    "top": msg_top,
                })
            except Exception:
                continue
        return items

    def _collect_reel_messages(self) -> list[dict]:
        items = []
        reel_shares = self.device(resourceId="com.instagram.android:id/reel_share_item_view")
        for j in range(reel_shares.count):
            try:
                reel = reel_shares[j]
                reel_bounds = reel.info.get("bounds", {})
                reel_left = reel_bounds.get("left", 0)
                reel_top = reel_bounds.get("top", 0)
                is_received = reel_left < self.screen_width * 0.25

                reel_author = self._extract_reel_author(reel_bounds)
                items.append({
                    "type": "reel",
                    "text": f"[Reel de @{reel_author}]" if reel_author else "[Reel partagé]",
                    "is_sent": not is_received,
                    "top": reel_top,
                })
            except Exception:
                continue
        return items

    def _extract_reel_author(self, reel_bounds: dict) -> str:
        title_elem = self.device(resourceId="com.instagram.android:id/title_text")
        for k in range(title_elem.count):
            try:
                title = title_elem[k]
                title_bounds = title.info.get("bounds", {})
                if (
                    title_bounds.get("top", 0) >= reel_bounds.get("top", 0)
                    and title_bounds.get("bottom", 0) <= reel_bounds.get("bottom", 0)
                ):
                    return title.get_text() or ""
            except Exception:
                continue
        return ""


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
