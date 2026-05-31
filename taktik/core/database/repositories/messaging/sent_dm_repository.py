"""Repository for sent DM duplicate prevention."""

from __future__ import annotations

import hashlib
from typing import Optional

from taktik.core.database.repositories._base.base_repository import BaseRepository


class SentDMRepository(BaseRepository):
    """Persist sent direct messages across supported social platforms."""

    def ensure_table(self) -> None:
        """Create the legacy table when the bot runs against a standalone DB."""
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_dms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                recipient_username TEXT NOT NULL,
                message_hash TEXT,
                sent_at TEXT DEFAULT (datetime('now')),
                success INTEGER DEFAULT 1,
                error_message TEXT,
                session_id TEXT,
                platform TEXT DEFAULT 'instagram',
                UNIQUE(account_id, recipient_username, platform)
            )
            """
        )

    def check_already_sent(self, account_id: int, recipient: str, platform: str = "instagram") -> bool:
        """Return whether a DM was already sent to this recipient on a platform."""
        self.ensure_table()
        result = self.query_one(
            """
            SELECT id
            FROM sent_dms
            WHERE account_id = ? AND recipient_username = ? AND platform = ?
            """,
            (account_id, recipient.lower(), platform),
        )
        return result is not None

    def record(
        self,
        account_id: int,
        recipient: str,
        message: str,
        success: bool,
        error_message: Optional[str] = None,
        session_id: Optional[str] = None,
        platform: str = "instagram",
    ) -> None:
        """Record a sent DM marker for duplicate prevention."""
        self.ensure_table()
        message_hash = hashlib.sha256(message.encode()).hexdigest() if message else None

        self.execute(
            """
            INSERT OR REPLACE INTO sent_dms (
                account_id,
                recipient_username,
                message_hash,
                success,
                error_message,
                session_id,
                platform
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                recipient.lower(),
                message_hash,
                1 if success else 0,
                error_message,
                session_id,
                platform,
            ),
        )


__all__ = ["SentDMRepository"]
