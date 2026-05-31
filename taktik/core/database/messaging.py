"""Database facades for cross-platform messaging bookkeeping."""

from __future__ import annotations

import os
import sqlite3
from typing import Optional

from loguru import logger

from taktik.core.database.local.paths import get_default_database_path
from taktik.core.database.repositories.messaging import SentDMRepository


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


__all__ = ["SentDMService"]
