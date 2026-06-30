"""Database facades for cross-platform messaging bookkeeping."""

from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List, Optional

from loguru import logger

from taktik.core.database.local.paths import get_default_database_path
from taktik.core.database.repositories.messaging import (
    SentDMRepository,
    DmThreadRepository,
    DmMessageRepository,
)


class SentDMService:
    """Compatibility service for bridge DM duplicate prevention."""

    @staticmethod
    def _open_repository() -> tuple[SentDMRepository, sqlite3.Connection] | None:
        db_path = get_default_database_path()
        if not os.path.exists(db_path):
            return None

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return SentDMRepository(conn), conn

    @staticmethod
    def check_already_sent(account_id: int, recipient: str, platform: str = "instagram") -> bool:
        """Check if a DM was already sent to this recipient on the given platform."""
        opened = SentDMService._open_repository()
        if opened is None:
            return False

        repo, conn = opened
        try:
            return repo.check_already_sent(account_id, recipient, platform)
        except Exception as exc:
            logger.warning(f"Error checking sent DMs: {exc}")
            return False
        finally:
            conn.close()

    @staticmethod
    def record(
        account_id: int,
        recipient: str,
        message: str,
        success: bool,
        error_message: Optional[str] = None,
        session_id: Optional[str] = None,
        platform: str = "instagram",
    ) -> None:
        """Record a sent DM in the database."""
        opened = SentDMService._open_repository()
        if opened is None:
            logger.warning(f"Database not found at {get_default_database_path()}")
            return

        repo, conn = opened
        try:
            repo.record(account_id, recipient, message, success, error_message, session_id, platform)
            logger.info(f"Recorded DM to {recipient} in database")
        except Exception as exc:
            logger.warning(f"Error recording sent DM: {exc}")
        finally:
            conn.close()


class DmConversationService:
    """Persist DM conversations + messages (read + sent), cross-platform.

    Coordinator: opens one connection and orchestrates the thread/message repositories.
    SECURITY: never logs DM content — only counts / usernames (AGENTS.md).
    Source of truth is the Bot; Electron reads these tables (read-only) and Turso syncs them.
    """

    @staticmethod
    def _open() -> Optional[sqlite3.Connection]:
        db_path = get_default_database_path()
        if not os.path.exists(db_path):
            logger.warning(f"Database not found at {db_path}")
            return None
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def record_conversation(
        *,
        platform: str,
        account_id: int,
        partner_username: str,
        messages: List[Dict[str, Any]],
        partner_profile_id: Optional[int] = None,
        external_thread_id: Optional[str] = None,
        is_group: bool = False,
        can_reply: bool = True,
        last_message_is_ours: bool = False,
        unread_count: int = 0,
    ) -> Optional[str]:
        """Upsert a read conversation + its messages. Return the thread sync_id.

        ``messages`` items: {direction: 'sent'|'received', text, msg_type?, ai_model?, ai_cost_usd?}.
        """
        conn = DmConversationService._open()
        if conn is None:
            return None
        try:
            threads = DmThreadRepository(conn)
            msg_repo = DmMessageRepository(conn)
            last = messages[-1] if messages else {}
            thread_sync_id = threads.upsert(
                platform=platform,
                account_id=account_id,
                partner_username=partner_username,
                partner_profile_id=partner_profile_id,
                external_thread_id=external_thread_id,
                is_group=is_group,
                can_reply=can_reply,
                last_message_text=last.get("text"),
                # Raw IG label of the last message (display); sortable order stays on updated_at.
                last_message_at=last.get("displayed_at"),
                last_message_is_ours=last_message_is_ours,
                unread_count=unread_count,
                message_count=len(messages),
            )
            for index, message in enumerate(messages):
                msg_repo.add_message(
                    platform=platform,
                    thread_sync_id=thread_sync_id,
                    account_id=account_id,
                    partner_username=partner_username,
                    direction=message.get("direction", "received"),
                    text=message.get("text"),
                    msg_type=message.get("msg_type", "text"),
                    seq=index,
                    # sent_at left to its insertion-time default (sortable); the raw IG label
                    # goes to displayed_at for display only.
                    displayed_at=message.get("displayed_at"),
                    ai_model=message.get("ai_model"),
                    ai_cost_usd=message.get("ai_cost_usd"),
                )
            logger.info(f"Recorded DM conversation with {partner_username} ({len(messages)} messages)")
            return thread_sync_id
        except Exception as exc:
            logger.warning(f"Error recording DM conversation: {exc}")
            return None
        finally:
            conn.close()

    @staticmethod
    def lookup_account_id(platform: str, partner_username: str) -> Optional[int]:
        """Return the account that owns an existing thread with this interlocutor, if any."""
        conn = DmConversationService._open()
        if conn is None:
            return None
        try:
            return DmThreadRepository(conn).find_account_id(platform, partner_username)
        except Exception as exc:
            logger.warning(f"Error looking up DM account: {exc}")
            return None
        finally:
            conn.close()

    @staticmethod
    def last_known_message(
        platform: str, account_id: int, inbox_username: str
    ) -> Optional[Dict[str, Any]]:
        """Return the stored last message ``{text, is_ours}`` of a known thread, or None.

        Lets the DM reader short-circuit a conversation whose last message is already on
        record (no new activity) instead of re-opening and scrolling the whole thread.
        """
        conn = DmConversationService._open()
        if conn is None:
            return None
        try:
            return DmThreadRepository(conn).find_last_message(platform, account_id, inbox_username)
        except Exception as exc:
            logger.warning(f"Error looking up DM last message: {exc}")
            return None
        finally:
            conn.close()

    @staticmethod
    def thread_answer_state(
        platform: str, account_id: int, inbox_username: str, limit: int = 30
    ) -> Dict[str, Any]:
        """Whether WE already answered a thread and which incoming messages are on record.

        Returns ``{has_sent, received_texts}``. ``has_sent`` is the reliable 'we answered'
        signal (read from dm_messages, immune to the dm_threads.last_message_is_ours flag that
        an ephemeral re-read can clobber). The reader uses this to keep a thread answered when IG
        vanish-mode hid our reply and no NEW incoming message has arrived.
        """
        empty: Dict[str, Any] = {"has_sent": False, "received_texts": []}
        conn = DmConversationService._open()
        if conn is None:
            return empty
        try:
            sync_id = DmThreadRepository(conn).find_sync_id_for_inbox(platform, account_id, inbox_username)
            if not sync_id:
                return empty
            messages = DmMessageRepository(conn)
            return {
                "has_sent": messages.has_sent_message(platform, sync_id),
                "received_texts": messages.received_texts(platform, sync_id, limit),
            }
        except Exception as exc:
            logger.warning(f"Error reading DM thread answer state: {exc}")
            return empty
        finally:
            conn.close()

    @staticmethod
    def mark_thread_answered(platform: str, account_id: int, inbox_username: str) -> bool:
        """Re-assert that WE answered a thread (last_message_is_ours, can_reply=False) when an
        ephemeral re-read downgraded it. Bot-owned fact write; returns True if a row changed."""
        conn = DmConversationService._open()
        if conn is None:
            return False
        try:
            return DmThreadRepository(conn).mark_answered(platform, account_id, inbox_username)
        except Exception as exc:
            logger.warning(f"Error marking DM thread answered: {exc}")
            return False
        finally:
            conn.close()

    @staticmethod
    def record_sent_message(
        *,
        platform: str,
        account_id: int,
        partner_username: str,
        text: str,
        partner_profile_id: Optional[int] = None,
        ai_model: Optional[str] = None,
        ai_cost_usd: Optional[float] = None,
    ) -> Optional[str]:
        """Append one reply we sent + refresh the thread's last message."""
        conn = DmConversationService._open()
        if conn is None:
            return None
        try:
            threads = DmThreadRepository(conn)
            msg_repo = DmMessageRepository(conn)
            thread_sync_id = threads.upsert(
                platform=platform,
                account_id=account_id,
                partner_username=partner_username,
                partner_profile_id=partner_profile_id,
                last_message_text=text,
                last_message_is_ours=True,
                # We just answered → the thread is no longer awaiting a reply from us. Without
                # this, upsert's can_reply default (True) left answered threads "replyable".
                can_reply=False,
            )
            msg_repo.add_message(
                platform=platform,
                thread_sync_id=thread_sync_id,
                account_id=account_id,
                partner_username=partner_username,
                direction="sent",
                text=text,
                # Append after the existing thread messages (else seq=0 would sort it first).
                seq=msg_repo.next_seq(platform, thread_sync_id),
                ai_model=ai_model,
                ai_cost_usd=ai_cost_usd,
            )
            logger.info(f"Recorded sent DM to {partner_username}")
            return thread_sync_id
        except Exception as exc:
            logger.warning(f"Error recording sent DM message: {exc}")
            return None
        finally:
            conn.close()


__all__ = ["SentDMService", "DmConversationService"]
