"""Repository for account restriction signals (one row per detection)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from taktik.core.database.repositories._base.base_repository import BaseRepository
from taktik.core.database.local.schemas.account_restrictions import (
    create_account_restriction_tables,
    create_account_restriction_indexes,
)


class AccountRestrictionRepository(BaseRepository):
    """Persist the observable trace that Instagram flagged one of our accounts.

    Write-mostly: the Bot records a detection, the desktop reads the history to say how
    long an account has been affected and whether it has stopped. One row per detection
    rather than per session, because the number of jumps a run needed is itself the
    measure of how deep the poisoned zone was.
    """

    def ensure_table(self) -> None:
        """Create the table when the bot runs against a standalone DB."""
        cursor = self._conn.cursor()
        create_account_restriction_tables(cursor)
        create_account_restriction_indexes(cursor)
        self._conn.commit()

    def record_signal(
        self,
        account_username: str,
        *,
        platform: str = "instagram",
        signal: str = "private_first_ordering",
        source_type: Optional[str] = None,
        source_name: Optional[str] = None,
        source_followers: Optional[int] = None,
        streak: Optional[int] = None,
        encounter_order: Optional[int] = None,
        jump_index: Optional[int] = None,
        gestures: Optional[int] = None,
        session_id: Optional[int] = None,
    ) -> bool:
        """Record one detection. Never raises: a measurement must not break a run."""
        if not account_username:
            return False
        try:
            self.ensure_table()
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO account_restriction_signals
                    (platform, account_username, signal, source_type, source_name,
                     source_followers, streak, encounter_order, jump_index, gestures, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (platform, account_username, signal, source_type, source_name,
                 source_followers, streak, encounter_order, jump_index, gestures, session_id),
            )
            self._conn.commit()
            return True
        except Exception as exc:  # noqa: BLE001
            # Deliberately swallowed: losing one measurement is acceptable, losing the run
            # that produced it is not.
            logger.debug(f"Could not record restriction signal: {exc}")
            return False

    def recent_signals(
        self, account_username: str, platform: str = "instagram", limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Most recent detections first — what the account panel reads."""
        try:
            self.ensure_table()
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT detected_at, signal, source_type, source_name, source_followers,
                       streak, encounter_order, jump_index, gestures
                FROM account_restriction_signals
                WHERE platform = ? AND account_username = ?
                ORDER BY detected_at DESC
                LIMIT ?
                """,
                (platform, account_username, limit),
            )
            columns = [d[0] for d in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Could not read restriction signals: {exc}")
            return []


__all__ = ["AccountRestrictionRepository"]
