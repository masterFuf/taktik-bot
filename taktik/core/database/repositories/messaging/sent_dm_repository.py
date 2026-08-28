"""Repository for sent DM duplicate prevention."""

from __future__ import annotations

import hashlib
from typing import Optional

from taktik.core.database.repositories._base.base_repository import BaseRepository


class SentDMRepository(BaseRepository):
    """Persist sent direct messages across supported social platforms."""

    def ensure_table(self) -> None:
        """Create the legacy table when the bot runs against a standalone DB, and migrate it.

        `CREATE TABLE IF NOT EXISTS` is not a schema migration, and treating it as one is what
        broke the duplicate guard on every existing database: the `platform` column below was
        added to this statement long after the table had been created, so it was never applied.
        Both queries then failed with `no such column: platform`, and `SentDMService` catches
        Exception and answers False — "never messaged". Instagram cold DM had no duplicate
        protection at all.

        The desktop owns the real migration (`migrations.ts`); this keeps a standalone bot
        working on a database the desktop has never opened.
        """
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
        self._add_platform_column_if_missing()

    def _add_platform_column_if_missing(self) -> None:
        """Additive and idempotent. Existing rows are Instagram — the only writer there ever was."""
        try:
            if self.column_exists("sent_dms", "platform"):
                return
        except Exception:
            return
        try:
            self.execute("ALTER TABLE sent_dms ADD COLUMN platform TEXT DEFAULT 'instagram'")
        except Exception:
            # Another process may have added it between the read and the write.
            return

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
