"""Repository for sent DM duplicate prevention."""

from __future__ import annotations

import hashlib
from typing import Optional

from taktik.core.database.repositories._base.base_repository import BaseRepository


#: A marker, written with its sync key.
_RECORD = """
    INSERT OR REPLACE INTO sent_dms (
        account_id, recipient_username, message_hash, success, error_message, session_id, platform, sync_id
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, lower(hex(randomblob(16))))
"""

#: The same marker on a base without the sync column: the statement above, its key taken out.
_RECORD_WITHOUT_SYNC_KEY = _RECORD.replace(", sync_id", "").replace(", lower(hex(randomblob(16)))", "")


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
        """Record a sent DM marker for duplicate prevention, with its sync key.

        Turso pushes only the rows that carry a `sync_id` (`lower(hex(randomblob(16)))`, as the other
        repositories of synced tables write it): a marker written without one never left the PC. A
        marker recorded again replaces the row, under a new key: the table is append-only on Turso.
        A base the desktop has never opened (the bot's old steps, `ensure_table`) has no sync column
        and nothing syncs from it: there the marker is recorded without a key.
        """
        self.ensure_table()
        message_hash = hashlib.sha256(message.encode()).hexdigest() if message else None
        statement = _RECORD if self.column_exists("sent_dms", "sync_id") else _RECORD_WITHOUT_SYNC_KEY

        self.execute(
            statement,
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
