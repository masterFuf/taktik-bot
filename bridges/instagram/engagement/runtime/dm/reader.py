"""DM conversation reading and message extraction for the Instagram DM bridge."""

from __future__ import annotations

import time

from bridges.instagram.engagement.runtime.dm.conversation_payload import (
    build_answered_conversation,
    build_conversation_payload,
    build_up_to_date_conversation,
    extract_inbox_username,
    has_unseen_incoming,
    inbox_preview_matches_known,
    is_already_processed,
    is_outgoing_last_message,
    masked_preview,
    normalize_inbox_username,
    sort_threads_by_top,
)
from bridges.instagram.engagement.runtime.dm.conversation_state import DMConversationStateMixin
from bridges.instagram.engagement.runtime.dm.events import emit_dm_json
from bridges.instagram.engagement.runtime.dm.message_extraction import DMMessageExtractionMixin
from bridges.instagram.engagement.runtime.dm.persistence import (
    last_known_message,
    mark_thread_answered,
    thread_answer_state,
)
from bridges.instagram.runtime.ipc import logger
from taktik.core.shared.behavior.gesture_primitives import human_scroll_raw
from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


class DMConversationReaderMixin(DMConversationStateMixin, DMMessageExtractionMixin):
    """Read DM conversations and extract visible message history."""

    def read_conversations(self, limit: int) -> list:
        """Read DM conversations. ``limit <= 0`` means read all (until the inbox bottom)."""
        conversations = []
        processed_usernames = set()
        processed_real_usernames = set()
        conversations_read = 0
        scroll_count = 0
        read_all = limit <= 0
        max_scrolls = 30 if read_all else 10

        while (read_all or conversations_read < limit) and scroll_count < max_scrolls:
            threads = self.device.xpath(DM_SELECTORS.thread_container).all()

            if not threads:
                logger.warning("No threads found")
                break

            threads_with_pos = sort_threads_by_top(threads)

            new_conversations_in_scroll = 0

            for thread_top, thread in threads_with_pos:
                if not read_all and conversations_read >= limit:
                    break

                try:
                    thread_info = thread.info
                    content_desc = thread_info.get("contentDescription", "")
                    username = extract_inbox_username(content_desc)
                    username = self._resolve_thread_username(thread_info, username)

                    username_lower, username_base = normalize_inbox_username(username)
                    if is_already_processed(username_base, processed_usernames):
                        logger.debug(f"Skipping already processed: {username}")
                        continue

                    # Smart triage: if WE sent the last message (row digest "Sent…"/"Envoyé…"),
                    # don't reopen the thread — emit a lightweight "answered" conv (the front
                    # restores the full history from the DB). Faster re-reads + accurate triage.
                    if is_outgoing_last_message(content_desc, username, DM_SELECTORS.outgoing_digest_prefixes):
                        processed_usernames.add(username_lower)
                        conv = build_answered_conversation(real_username=username, inbox_username=username)
                        conversations.append(conv)
                        conversations_read += 1
                        new_conversations_in_scroll += 1
                        emit_dm_json(
                            {
                                "type": "conversation",
                                "current": conversations_read,
                                "total": max(limit, 0),
                                "conversation": conv,
                            },
                            flush=True,
                        )
                        logger.info(f"Skipping (already answered, we sent last): {username}")
                        continue

                    # Early-exit (no new activity): if the inbox row's last message is the same
                    # one already on record for this thread (received OR sent), there is nothing
                    # new — skip opening/scrolling and move on. The front restores the full
                    # history from the DB. The match is conservative (see
                    # inbox_preview_matches_known): it never skips a genuine new reply.
                    account_id = getattr(self, "_dm_account_id", None)
                    known = last_known_message(account_id, username)
                    matched = bool(known) and inbox_preview_matches_known(content_desc, username, known["text"])
                    # Safe diagnostic (masked = no DM content): why does the early-exit skip or not?
                    logger.info(
                        f"[DM] pre-open {username_lower}: in_db={bool(known)} skip={matched} "
                        f"shape='{masked_preview(content_desc)}'"
                    )
                    if matched:
                        processed_usernames.add(username_lower)
                        # No new activity. Classify answered/replyable from the RELIABLE message
                        # order (the thread's last_message_is_ours flag can be clobbered by an
                        # ephemeral re-read); if WE answered, re-assert it in the DB so the front
                        # doesn't re-propose a reply. Either way we skip without opening/scrolling.
                        answer_state = thread_answer_state(account_id, username)
                        answered = answer_state["last_direction"] == "sent"
                        if answered:
                            mark_thread_answered(account_id, username)
                        conv = build_up_to_date_conversation(
                            real_username=username,
                            inbox_username=username,
                            last_is_ours=answered,
                        )
                        conversations.append(conv)
                        conversations_read += 1
                        new_conversations_in_scroll += 1
                        emit_dm_json(
                            {
                                "type": "conversation",
                                "current": conversations_read,
                                "total": max(limit, 0),
                                "conversation": conv,
                            },
                            flush=True,
                        )
                        emit_dm_json(
                            {
                                "type": "conversation_skipped",
                                "reason": "up_to_date",
                                "username": username,
                                "last_message_is_ours": answered,
                                "current": conversations_read,
                                "total": max(limit, 0),
                            },
                            flush=True,
                        )
                        logger.info(f"Skipping (up to date, last message already known): {username}")
                        continue

                    logger.info(f"Opening conversation: {username}")
                    if not tap_element_human(self.device, thread, logger=logger):
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

                    conv = build_conversation_payload(
                        real_username=real_username,
                        inbox_username=username,
                        messages=messages,
                        is_group=is_group,
                        can_reply=can_reply,
                    )
                    if conv["last_message_is_ours"]:
                        logger.info(f"Dernier message de @{real_username} est de NOUS -> can_reply=False")

                    # Vanish-mode safety net: IG ephemeral messages can hide OUR last sent message,
                    # so a thread we already answered re-reads as "reply possible" (a prior re-read
                    # may even have downgraded the stored thread). If a sent message is on record
                    # AND no NEW incoming message is visible, keep it answered and re-assert it in
                    # the DB (else the front's DB merge re-proposes a reply). `known` is reused from
                    # the early-exit lookup (None => brand-new thread, nothing to reconcile).
                    if not conv["last_message_is_ours"] and known:
                        state = thread_answer_state(account_id, username)
                        if state["last_direction"] == "sent" and not has_unseen_incoming(messages, state["received_texts"]):
                            logger.info(
                                f"@{real_username}: deja repondu (reponse masquee par le mode ephemere) "
                                "-> pas de relance"
                            )
                            mark_thread_answered(account_id, username)
                            conv = build_up_to_date_conversation(
                                real_username=real_username,
                                inbox_username=username,
                                last_is_ours=True,
                            )

                    conversations.append(conv)
                    conversations_read += 1
                    new_conversations_in_scroll += 1

                    emit_dm_json(
                        {
                            "type": "conversation",
                            "current": conversations_read,
                            # 0 total signals "all" to the front (indeterminate progress).
                            "total": max(limit, 0),
                            "conversation": conv,
                        },
                        flush=True,
                    )

                    self._go_back_from_conversation(delay=1.5)

                except Exception as e:
                    logger.error(f"Error reading conversation: {e}")
                    self._return_to_inbox_if_needed()
                    continue

            if not read_all and conversations_read >= limit:
                break

            if self._is_accounts_to_follow_visible():
                logger.info("Reached bottom of DM inbox (Accounts to follow visible), stopping read")
                break

            if new_conversations_in_scroll == 0:
                logger.info("No new conversations found in current inbox viewport, stopping read")
                break

            scroll_count += 1
            human_scroll_raw(self.device, "down", logger=logger)
            time.sleep(1.5)

        return conversations
