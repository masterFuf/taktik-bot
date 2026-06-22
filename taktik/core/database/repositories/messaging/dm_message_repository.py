"""Repository for DM messages (append-only, linked to a thread)."""

from __future__ import annotations

import hashlib
from typing import Optional

from taktik.core.database.repositories._base.base_repository import BaseRepository
from taktik.core.database.local.schemas.messaging import (
    create_messaging_tables,
    create_messaging_indexes,
)


def _content_hash(direction: str, text: Optional[str]) -> str:
    """Stable per-message key for re-read dedup (no server message id available)."""
    return hashlib.sha256(f"{direction}\n{text or ''}".encode()).hexdigest()


class DmMessageRepository(BaseRepository):
    """Append DM messages. Dedup by (thread, direction, content) on re-read."""

    def ensure_table(self) -> None:
        cursor = self._conn.cursor()
        create_messaging_tables(cursor)
        create_messaging_indexes(cursor)
        self._conn.commit()

    def next_seq(self, platform: str, thread_sync_id: str) -> int:
        """Next display index for a thread (MAX(seq)+1) so an appended reply sorts last."""
        self.ensure_table()
        row = self.query_one(
            "SELECT MAX(seq) AS max_seq FROM dm_messages "
            "WHERE platform = ? AND thread_sync_id = ?",
            (platform, thread_sync_id),
        )
        current = row["max_seq"] if row and row["max_seq"] is not None else -1
        return int(current) + 1

    def add_message(
        self,
        *,
        platform: str,
        thread_sync_id: str,
        direction: str,
        text: Optional[str],
        account_id: Optional[int] = None,
        partner_username: Optional[str] = None,
        msg_type: str = "text",
        seq: int = 0,
        sent_at: Optional[str] = None,
        displayed_at: Optional[str] = None,
        ai_model: Optional[str] = None,
        ai_cost_usd: Optional[float] = None,
    ) -> bool:
        """Insert one message (idempotent on re-read). Return True if a new row was written.

        ``sent_at`` stays a sortable datetime (insertion time fallback / sync delta cursor);
        ``displayed_at`` is the raw IG date/time label kept only for display.
        """
        self.ensure_table()
        cursor = self.execute(
            """
            INSERT OR IGNORE INTO dm_messages (
                platform, thread_sync_id, account_id, partner_username, direction, msg_type,
                text, content_hash, seq, sent_at, displayed_at, ai_model, ai_cost_usd, sync_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now')), ?, ?, ?, lower(hex(randomblob(16))))
            """,
            (
                platform,
                thread_sync_id,
                account_id,
                partner_username.lower() if partner_username else None,
                direction,
                msg_type,
                text,
                _content_hash(direction, text),
                seq,
                sent_at,
                displayed_at,
                ai_model,
                ai_cost_usd,
            ),
        )
        return cursor.rowcount > 0


__all__ = ["DmMessageRepository"]
