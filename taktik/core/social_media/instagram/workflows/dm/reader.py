"""DM conversation reading and message extraction for the Instagram DM inbox."""

from __future__ import annotations

import time

from taktik.core.social_media.instagram.workflows.dm.conversation_payload import (
    build_answered_conversation,
    build_conversation_payload,
    build_up_to_date_conversation,
    extract_inbox_username,
    has_unseen_incoming,
    inbox_preview_matches_known,
    is_outgoing_last_message,
    masked_preview,
    sort_threads_by_top,
)
from taktik.core.shared.text import same_shown_name
from taktik.core.social_media.instagram.workflows.dm.conversation_state import DMConversationStateMixin
from taktik.core.social_media.instagram.workflows.dm.message_extraction import DMMessageExtractionMixin
from taktik.core.social_media.instagram.workflows.dm.persistence import (
    mark_thread_answered,
    thread_answer_state,
)
from loguru import logger
from taktik.core.shared.behavior.gesture_primitives import human_scroll_raw
from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from taktik.core.social_media.instagram.workflows.dm.session import dm_inbox_shown
from taktik.core.shared.device.ui_dump import whole_in_band


def _bounds_of(element):
    """(left, top, right, bottom) of a uiautomator2 element, or None when it gives none."""
    bounds = element.info.get("bounds") or {}
    if not bounds:
        return None
    return bounds.get("left", 0), bounds.get("top", 0), bounds.get("right", 0), bounds.get("bottom", 0)


class DMConversationReaderMixin(DMConversationStateMixin, DMMessageExtractionMixin):
    """Read DM conversations and extract visible message history."""

    def _thread_list_band(self):
        """(top, bottom) of the inbox's thread list on screen, or None when it is not found (the
        rows are then taken as they come)."""
        thread_list = self.device.xpath(DM_SELECTORS.inbox_thread_list)
        if not thread_list.exists:
            logger.debug("No thread list on screen: the rows are not bounded by it")
            return None
        bounds = _bounds_of(thread_list)
        return (bounds[1], bounds[3]) if bounds else None

    def _announce_conversation(self, conversation: dict, *, current: int, total: int) -> None:
        """One conversation read (or restored), for the desktop."""
        self._emit_dm_event(
            {"type": "conversation", "current": current, "total": total, "conversation": conversation},
            flush=True,
        )

    def _announce_up_to_date(self, username: str, *, answered: bool, current: int, total: int) -> None:
        """A thread left closed: its last message is already on record."""
        self._emit_dm_event(
            {"type": "conversation_skipped", "reason": "up_to_date", "username": username,
             "last_message_is_ours": answered, "current": current, "total": total},
            flush=True,
        )

    def read_conversations(self, limit: int) -> list | None:
        """Read DM conversations. ``limit <= 0`` means read all (until the inbox bottom).

        None, and nothing read, when the screen is not the inbox (or its requests folder): an
        inbox not on screen is no empty inbox (Lab `dm.list_unread` on a conversation, Pixel 6 Pro,
        2026-10-24: « No threads found », then « 0 conversation(s) read » as a success).
        """
        if not dm_inbox_shown(self.device):
            logger.error("The DM inbox is not on screen: no conversation read")
            return None
        conversations = []
        # The names of the rows read in this pass, as shown: a row is left when its name is one of
        # them (`same_shown_name`), never when its name only starts like one.
        processed_usernames: list[str] = []
        processed_real_usernames = set()
        conversations_read = 0
        scroll_count = 0
        read_all = limit <= 0
        max_scrolls = 30 if read_all else 10

        while (read_all or conversations_read < limit) and scroll_count < max_scrolls:
            threads = self.device.xpath(DM_SELECTORS.thread_container).all()

            if not threads:
                if dm_inbox_shown(self.device):
                    logger.warning("No threads found")
                else:
                    logger.error(f"The DM inbox is no longer on screen: reading stopped after "
                                 f"{conversations_read} conversation(s)")
                break

            # Only the rows whole inside the thread list: a row cut by its bottom runs under the tab
            # bar, and a tap on it opened the tab bar's search (Pixel 6a, 447, 2026-10-24: « Could
            # not open conversation », then the inbox lost). It is read whole after the next scroll.
            band = self._thread_list_band()
            threads_with_pos = [(top, thread) for top, thread in sort_threads_by_top(threads)
                                if band is None or whole_in_band(_bounds_of(thread), band)]

            new_conversations_in_scroll = 0

            for thread_top, thread in threads_with_pos:
                if not read_all and conversations_read >= limit:
                    break

                try:
                    thread_info = thread.info
                    content_desc = thread_info.get("contentDescription", "")
                    username = extract_inbox_username(content_desc)
                    username = self._resolve_thread_username(thread_info, username)

                    if any(same_shown_name(username, seen) for seen in processed_usernames):
                        logger.debug(f"Skipping already processed: {username}")
                        continue

                    # Smart triage: if WE sent the last message (row digest "Sent…"/"Envoyé…"),
                    # don't reopen the thread — emit a lightweight "answered" conv (the front
                    # restores the full history from the DB). Faster re-reads + accurate triage.
                    if is_outgoing_last_message(content_desc, username, DM_SELECTORS.outgoing_digest_prefixes):
                        processed_usernames.append(username)
                        conv = build_answered_conversation(real_username=username, inbox_username=username)
                        conversations.append(conv)
                        conversations_read += 1
                        new_conversations_in_scroll += 1
                        self._announce_conversation(conv, current=conversations_read, total=max(limit, 0))
                        logger.info(f"Skipping (already answered, we sent last): {username}")
                        continue

                    # Early-exit (no new activity): if the inbox row's last message is the same
                    # one already on record for this thread (received OR sent), there is nothing
                    # new — skip opening/scrolling and move on. The front restores the full
                    # history from the DB. The match is conservative (see
                    # inbox_preview_matches_known): it never skips a genuine new reply.
                    account_id = getattr(self, "_dm_account_id", None)
                    answer_state = thread_answer_state(account_id, username)
                    # Match the inbox-row preview against the messages we ACTUALLY have on record
                    # (dm_messages, both directions) — far more reliable than the denormalised
                    # dm_threads.last_message_text, which can be stale/clobbered. If the visible last
                    # message is one we already stored, there is no new activity.
                    matched = any(
                        inbox_preview_matches_known(content_desc, username, text)
                        for text in answer_state["recent_texts"]
                    )
                    # Safe diagnostic (masked = no DM content): why does the early-exit skip or not?
                    logger.info(
                        f"[DM] pre-open {username}: in_db={answer_state['last_direction'] is not None} "
                        f"skip={matched} shape='{masked_preview(content_desc)}'"
                    )
                    if matched:
                        processed_usernames.append(username)
                        # No new activity. Classify answered/replyable from the RELIABLE message order
                        # (the thread's last_message_is_ours flag can be clobbered by an ephemeral
                        # re-read); if WE answered, re-assert it in the DB so the front doesn't
                        # re-propose a reply. Either way we skip without opening/scrolling.
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
                        self._announce_conversation(conv, current=conversations_read, total=max(limit, 0))
                        self._announce_up_to_date(username, answered=answered, current=conversations_read,
                                                  total=max(limit, 0))
                        logger.info(f"Skipping (up to date, last message already known): {username}")
                        continue

                    logger.info(f"Opening conversation: {username}")
                    # Tap the row's TEXT area, not the left avatar: tapping the avatar opens the
                    # user's STORY (when they have an unseen-story ring) instead of the
                    # conversation, and the open fails.
                    if not tap_element_human(self.device, thread, logger=logger, x_min_frac=0.25):
                        thread.click()
                    time.sleep(2)

                    header_title = self.device(resourceId=DM_SELECTORS.conversation_header_title_resource_id)
                    if not header_title.exists(timeout=3):
                        logger.warning(f"Could not open conversation with {username}")
                        self._return_to_inbox_if_needed()
                        continue

                    # The thread is filed under the partner's handle: the header's title is
                    # their display name when they have one, the handle then under it.
                    shown_name, handle = self._read_conversation_partner()
                    if handle is None:
                        logger.info(f"No handle in the header of the conversation with {username}: "
                                    "filed under the name shown")
                    real_username = handle or shown_name or header_title.get_text() or username
                    real_username_lower = real_username.lower().strip()
                    if real_username_lower in processed_real_usernames:
                        logger.info(f"Skipping duplicate (real_username already seen): {real_username}")
                        self._go_back_from_conversation()
                        continue

                    processed_usernames.append(username)
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
                    # the DB (else the front's DB merge re-proposes a reply). Reuses answer_state
                    # from the pre-open lookup (last_direction None => brand-new thread, nothing to do).
                    if not conv["last_message_is_ours"] and answer_state["last_direction"] is not None:
                        if answer_state["last_direction"] == "sent" and not has_unseen_incoming(messages, answer_state["received_texts"]):
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

                    # 0 total signals "all" to the front (indeterminate progress).
                    self._announce_conversation(conv, current=conversations_read, total=max(limit, 0))

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
