"""Repository for actions WE took on notifications (like / reply / accept / ignore / follow_back).

One row per executed action, written by the notifications bridge at execution time.
LOCAL, not Turso-synced (notifications-autopilot-spec.md): the table's job is per-PC
idempotence (never re-treat a notification) and an audit trail of what the operator —
or later the autopilot — actually did. The budget-consuming counterpart of an action
(FOLLOW / COMMENT / COMMENT_LIKE) is written separately into ``interactions`` via the
canonical ``record_individual_actions`` facade; this table never replaces that.
"""

from __future__ import annotations

from typing import Optional, Set

from taktik.core.database.repositories._base.base_repository import BaseRepository
from taktik.core.database.local.schemas.notifications import (
    create_notifications_tables,
    create_notifications_indexes,
)


class NotificationActionRepository(BaseRepository):
    """Persist executed notification actions; answer "did we already do this?"."""

    def ensure_table(self) -> None:
        """Create the notifications tables when the bot runs against a standalone DB."""
        cursor = self._conn.cursor()
        create_notifications_tables(cursor)
        create_notifications_indexes(cursor)
        self._conn.commit()

    def record(
        self,
        *,
        platform: str,
        account_id: int,
        action: str,
        actor_username: Optional[str] = None,
        content_hash: Optional[str] = None,
        source: str = "manual",
        success: bool = True,
    ) -> None:
        """Insert one executed action. Failures are recorded too (success=0): a failed
        follow-back must not be silently retried forever by an autopilot — the caller
        decides retry policy from the audit trail, not from amnesia."""
        self.ensure_table()
        self.execute(
            """
            INSERT INTO notification_actions (
                platform, account_id, content_hash, actor_username, action, source, success
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                platform, account_id, content_hash,
                (actor_username or "").strip().lower() or None,
                action, source, 1 if success else 0,
            ),
        )

    def already_actioned(
        self, platform: str, account_id: int, content_hash: str, action: str,
    ) -> bool:
        """Whether this exact action already SUCCEEDED on this notification."""
        row = self.query_one(
            "SELECT 1 FROM notification_actions "
            "WHERE platform = ? AND account_id = ? AND content_hash = ? "
            "AND action = ? AND success = 1 LIMIT 1",
            (platform, account_id, content_hash, action),
        )
        return row is not None

    def actioned_hashes(self, platform: str, account_id: int, action: str) -> Set[str]:
        """All content_hashes on which ``action`` already succeeded for this account —
        preloaded once by a batch so the skip check costs no per-action DB hit."""
        rows = self.query(
            "SELECT DISTINCT content_hash FROM notification_actions "
            "WHERE platform = ? AND account_id = ? AND action = ? "
            "AND success = 1 AND content_hash IS NOT NULL",
            (platform, account_id, action),
        )
        return {row["content_hash"] for row in rows}


__all__ = ["NotificationActionRepository"]
