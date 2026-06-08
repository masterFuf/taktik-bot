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
        """Insert/refresh the Gmail account in the unified ``accounts`` table
        (platform='gmail') + its device sighting in ``account_device_history``.

        Vague F2: ``gmail_accounts`` is now a read-only compat view, so writes target
        the underlying tables. Best-effort (errors logged; callers tolerate failure).
        """
        try:
            conn = self._db._get_connection()
            cursor = conn.cursor()
            # accounts row (platform='gmail'). SELECT-then-act (no ON CONFLICT: the
            # accounts unique index isn't on (platform, username) on every base).
            row = cursor.execute(
                "SELECT legacy_account_id FROM accounts WHERE platform = 'gmail' AND username = ?",
                (email,),
            ).fetchone()
            if row:
                cursor.execute(
                    "UPDATE accounts SET updated_at = datetime('now') WHERE platform = 'gmail' AND username = ?",
                    (email,),
                )
            else:
                cursor.execute(
                    "SELECT COALESCE(MAX(legacy_account_id), 0) + 1 FROM accounts WHERE platform = 'gmail'"
                )
                next_id = cursor.fetchone()[0]
                cursor.execute(
                    """
                    INSERT INTO accounts (platform, legacy_account_id, username, is_bot, created_at, updated_at)
                    VALUES ('gmail', ?, ?, 0, datetime('now'), datetime('now'))
                    """,
                    (next_id, email),
                )
            if device_id:
                drow = cursor.execute(
                    "SELECT id FROM account_device_history "
                    "WHERE platform = 'gmail' AND username = ? AND device_id = ? AND package_name = ''",
                    (email, device_id),
                ).fetchone()
                if drow:
                    cursor.execute(
                        "UPDATE account_device_history SET last_seen_at = datetime('now'), "
                        "seen_count = seen_count + 1 WHERE id = ?",
                        (drow[0],),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO account_device_history
                            (platform, username, device_id, package_name, source, first_seen_at, last_seen_at, seen_count)
                        VALUES ('gmail', ?, ?, '', 'gmail', datetime('now'), datetime('now'), 1)
                        """,
                        (email, device_id),
                    )
            conn.commit()
            return True
        except Exception as e:
            logger.warning(f"Could not persist Gmail account {email!r}: {e}")
            return False

    def delete(self, email: str) -> bool:
        """Remove the Gmail account from the unified tables. Returns True on success."""
        try:
            conn = self._db._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM account_device_history WHERE platform = 'gmail' AND username = ?",
                (email,),
            )
            cursor.execute(
                "DELETE FROM accounts WHERE platform = 'gmail' AND username = ?",
                (email,),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning(f"Could not unpersist Gmail account {email!r}: {e}")
            return False


__all__ = ["GmailAccountRepository"]
