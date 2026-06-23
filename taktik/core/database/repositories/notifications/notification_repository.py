"""Repository for cross-platform notifications (one row per distinct notification)."""

from __future__ import annotations

import hashlib
from typing import Optional

from taktik.core.database.repositories._base.base_repository import BaseRepository
from taktik.core.database.local.schemas.notifications import (
    create_notifications_tables,
    create_notifications_indexes,
)


class NotificationRepository(BaseRepository):
    """Persist scanned notifications, deduplicated by a synthesized content hash.

    Notification rows have no stable server id, so re-scans are made idempotent with a
    ``content_hash`` over (platform, account, type, actor, body) and an INSERT OR IGNORE
    against ``UNIQUE(platform, account_id, content_hash)`` — exactly the approach used for
    ``dm_messages``. A re-seen notification only bumps ``last_seen_at``.
    """

    def ensure_table(self) -> None:
        """Create the notifications table when the bot runs against a standalone DB."""
        cursor = self._conn.cursor()
        create_notifications_tables(cursor)
        create_notifications_indexes(cursor)
        self._conn.commit()

    @staticmethod
    def content_hash(platform: str, account_id: int, ntype: Optional[str],
                     actor: Optional[str], body: Optional[str]) -> str:
        """Stable identity for a notification (no server id exists)."""
        raw = f"{platform}\n{account_id}\n{ntype or ''}\n{actor or ''}\n{body or ''}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def record(
        self,
        *,
        platform: str,
        account_id: int,
        actor_username: Optional[str] = None,
        actor_profile_id: Optional[int] = None,
        ntype: Optional[str] = None,
        raw_category: Optional[str] = None,
        label: Optional[str] = None,
        body: Optional[str] = None,
        relative_time: Optional[str] = None,
        has_action: bool = False,
        attributed: bool = False,
        attribution_type: Optional[str] = None,
        attribution_at: Optional[str] = None,
    ) -> bool:
        """Insert the notification if new (returns True); else bump last_seen_at (False)."""
        self.ensure_table()
        actor = (actor_username or "").strip().lower() or None
        chash = self.content_hash(platform, account_id, ntype, actor, body)
        cursor = self.execute(
            """
            INSERT OR IGNORE INTO notifications (
                platform, account_id, actor_username, actor_profile_id, type, raw_category,
                label, body, relative_time, has_action, attributed, attribution_type,
                attribution_at, content_hash, sync_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, lower(hex(randomblob(16))))
            """,
            (
                platform, account_id, actor, actor_profile_id, ntype, raw_category,
                label, body, relative_time, 1 if has_action else 0, 1 if attributed else 0,
                attribution_type, attribution_at, chash,
            ),
        )
        if cursor.rowcount and cursor.rowcount > 0:
            return True  # newly inserted
        # Already seen: refresh recency, keep the original first_seen_at.
        self.execute(
            "UPDATE notifications SET last_seen_at = datetime('now') "
            "WHERE platform = ? AND account_id = ? AND content_hash = ?",
            (platform, account_id, chash),
        )
        return False


__all__ = ["NotificationRepository"]
