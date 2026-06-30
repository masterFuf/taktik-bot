"""Repository for DM conversation threads (one row per conversation)."""

from __future__ import annotations

from typing import Optional

from taktik.core.database.repositories._base.base_repository import BaseRepository
from taktik.core.database.local.schemas.messaging import (
    create_messaging_tables,
    create_messaging_indexes,
)


class DmThreadRepository(BaseRepository):
    """Persist one row per DM conversation, keyed by (platform, account, interlocutor)."""

    def ensure_table(self) -> None:
        """Create the DM tables when the bot runs against a standalone DB."""
        cursor = self._conn.cursor()
        create_messaging_tables(cursor)
        create_messaging_indexes(cursor)
        self._conn.commit()

    def find_sync_id(self, platform: str, account_id: int, partner_username: str) -> Optional[str]:
        """Return the stable cross-device key of an existing thread, if any."""
        row = self.query_one(
            "SELECT sync_id FROM dm_threads "
            "WHERE platform = ? AND account_id = ? AND partner_username = ?",
            (platform, account_id, partner_username.lower()),
        )
        return row["sync_id"] if row else None

    def find_account_id(self, platform: str, partner_username: str) -> Optional[int]:
        """Account that owns the most recent thread with this interlocutor (if known).

        Lets the send path reuse the account resolved during a prior read instead of
        re-visiting our own profile on every reply.
        """
        row = self.query_one(
            "SELECT account_id FROM dm_threads "
            "WHERE platform = ? AND partner_username = ? "
            "ORDER BY updated_at DESC LIMIT 1",
            (platform, partner_username.lower()),
        )
        return row["account_id"] if row else None

    def find_last_message(
        self, platform: str, account_id: int, inbox_username: str
    ) -> Optional[dict]:
        """Stored last message of a known thread: ``{text, is_ours}``, or None.

        Matches either the persisted ``partner_username`` (the conversation header handle,
        lowercased) or the ``external_thread_id`` (the inbox-row username) so the reader can
        look it up from the inbox row BEFORE opening the thread. Lets the reader short-circuit
        a conversation whose last message is already on record (no new activity).
        """
        key = (inbox_username or "").strip()
        if not key:
            return None
        row = self.query_one(
            "SELECT last_message_text AS text, last_message_is_ours AS is_ours "
            "FROM dm_threads "
            "WHERE platform = ? AND account_id = ? "
            "AND (partner_username = ? OR external_thread_id = ? OR external_thread_id = ?) "
            "ORDER BY updated_at DESC LIMIT 1",
            (platform, account_id, key.lower(), key, key.lower()),
        )
        if not row or not row["text"]:
            return None
        return {"text": row["text"], "is_ours": bool(row["is_ours"])}

    def upsert(
        self,
        *,
        platform: str,
        account_id: int,
        partner_username: str,
        partner_profile_id: Optional[int] = None,
        external_thread_id: Optional[str] = None,
        is_group: bool = False,
        can_reply: bool = True,
        last_message_text: Optional[str] = None,
        last_message_at: Optional[str] = None,
        last_message_is_ours: bool = False,
        unread_count: int = 0,
        message_count: Optional[int] = None,
    ) -> str:
        """Insert or update the thread; return its ``sync_id`` (stable cross-device key)."""
        self.ensure_table()
        partner = partner_username.lower()
        existing = self.query_one(
            "SELECT sync_id FROM dm_threads "
            "WHERE platform = ? AND account_id = ? AND partner_username = ?",
            (platform, account_id, partner),
        )

        if existing is not None:
            sync_id = existing["sync_id"]
            self.execute(
                """
                UPDATE dm_threads SET
                    partner_profile_id = COALESCE(?, partner_profile_id),
                    external_thread_id = COALESCE(?, external_thread_id),
                    is_group = ?,
                    can_reply = ?,
                    last_message_text = COALESCE(?, last_message_text),
                    last_message_at = COALESCE(?, last_message_at),
                    last_message_is_ours = ?,
                    unread_count = ?,
                    message_count = COALESCE(?, message_count),
                    updated_at = datetime('now')
                WHERE sync_id = ?
                """,
                (
                    partner_profile_id,
                    external_thread_id,
                    1 if is_group else 0,
                    1 if can_reply else 0,
                    last_message_text,
                    last_message_at,
                    1 if last_message_is_ours else 0,
                    unread_count,
                    message_count,
                    sync_id,
                ),
            )
            return sync_id

        cursor = self.execute(
            """
            INSERT INTO dm_threads (
                platform, account_id, partner_username, partner_profile_id, external_thread_id,
                is_group, can_reply, last_message_text, last_message_at, last_message_is_ours,
                unread_count, message_count, sync_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, lower(hex(randomblob(16))))
            """,
            (
                platform,
                account_id,
                partner,
                partner_profile_id,
                external_thread_id,
                1 if is_group else 0,
                1 if can_reply else 0,
                last_message_text,
                last_message_at,
                1 if last_message_is_ours else 0,
                unread_count,
                message_count or 0,
            ),
        )
        row = self.query_one("SELECT sync_id FROM dm_threads WHERE id = ?", (cursor.lastrowid,))
        return row["sync_id"]


__all__ = ["DmThreadRepository"]
