"""Account repositories for Google-backed bridges (Gmail, YouTube).

Centralizes the `gmail_accounts` upsert/delete logic that used to live as
copy-pasted private helpers in both `gmail_account_bridge.py` and
`youtube_account_bridge.py`. Gmail and YouTube share the same Google account
identifier so a single table is enough.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger


class GmailAccountRepository:
    """SQLite repository for the `gmail_accounts` table.

    Wraps the LocalDatabaseService connection so bridges no longer need to
    reach for the private `_get_connection()` helper directly.
    """

    def __init__(self):
        from taktik.core.database.local.service import get_local_database
        self._db = get_local_database()

    def upsert(self, email: str, device_id: str) -> bool:
        """Insert the account or refresh its `device_id` / `last_used_at`.

        Returns True on success, False on any DB error (the error is logged
        via loguru — callers should treat persistence as best-effort).
        """
        try:
            conn = self._db._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO gmail_accounts (email, device_id, last_used_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(email) DO UPDATE SET
                    device_id = excluded.device_id,
                    last_used_at = datetime('now')
                """,
                (email, device_id),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning(f"Could not persist Gmail account {email!r}: {e}")
            return False

    def delete(self, email: str) -> bool:
        """Remove the account row. Returns True on success, False on DB error."""
        try:
            conn = self._db._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM gmail_accounts WHERE email = ?", (email,))
            conn.commit()
            return True
        except Exception as e:
            logger.warning(f"Could not unpersist Gmail account {email!r}: {e}")
            return False


__all__ = ["GmailAccountRepository"]
