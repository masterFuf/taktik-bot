"""
Database utilities shared across bridge scripts.

Centralizes:
- get_db_path(): cross-platform path to the local SQLite database
- SentDMService: check/record sent DMs (used by cold_dm_bridge & dm_outreach_bridge)

Usage:
    from bridges.common.database import get_db_path, SentDMService

    # Get database path
    db_path = get_db_path()

    # Check / record sent DMs
    SentDMService.check_already_sent(account_id=1, recipient="user123", platform="instagram")
    SentDMService.record(account_id=1, recipient="user123", message="Hello!", success=True, platform="instagram")
"""

import os
import sys
import sqlite3
import hashlib
from typing import Optional
from loguru import logger


def get_db_path() -> str:
    """Get the path to the local SQLite database (cross-platform)."""
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', '')
        return os.path.join(appdata, 'taktik-desktop', 'taktik-data.db')
    elif sys.platform == 'darwin':
        return os.path.expanduser('~/Library/Application Support/taktik-desktop/taktik-data.db')
    else:
        return os.path.expanduser('~/.config/taktik-desktop/taktik-data.db')


def get_repository(repo_class):
    """Get a repository instance connected to the local SQLite database.
    
    Usage:
        from taktik.core.database.repositories.tiktok_repository import TikTokRepository
        repo = get_repository(TikTokRepository)
        repo.get_or_create_profile("someuser")
    """
    db_path = get_db_path()
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}")
    conn = sqlite3.connect(db_path)
    return repo_class(conn)


class SentDMService:
    """
    Check and record sent DMs in the local SQLite database.

    Supports multi-platform (instagram / tiktok) via the `platform` column.
    The UNIQUE constraint is (account_id, recipient_username, platform).
    """

    @staticmethod
    def check_already_sent(account_id: int, recipient: str, platform: str = 'instagram') -> bool:
        """Check if a DM was already sent to this recipient on the given platform."""
        db_path = get_db_path()
        if not os.path.exists(db_path):
            return False

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM sent_dms WHERE account_id = ? AND recipient_username = ? AND platform = ?",
                (account_id, recipient.lower(), platform)
            )
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception as e:
            logger.warning(f"Error checking sent DMs: {e}")
            return False

    @staticmethod
    def record(account_id: int, recipient: str, message: str, success: bool,
               error_message: str = None, session_id: str = None,
               platform: str = 'instagram') -> None:
        """Record a sent DM in the database."""
        db_path = get_db_path()
        if not os.path.exists(db_path):
            logger.warning(f"Database not found at {db_path}")
            return

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Create table if not exists (with platform column)
            cursor.execute("""
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
            """)

            message_hash = hashlib.md5(message.encode()).hexdigest() if message else None

            cursor.execute("""
                INSERT OR REPLACE INTO sent_dms (account_id, recipient_username, message_hash, success, error_message, session_id, platform)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (account_id, recipient.lower(), message_hash, 1 if success else 0, error_message, session_id, platform))

            conn.commit()
            conn.close()
            logger.info(f"Recorded DM to {recipient} in database")
        except Exception as e:
            logger.warning(f"Error recording sent DM: {e}")
