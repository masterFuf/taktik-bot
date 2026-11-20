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
    ``content_hash`` over the TIME/LANGUAGE-INDEPENDENT identity (platform, account, type, actor)
    and an INSERT OR IGNORE against ``UNIQUE(platform, account_id, content_hash)`` — exactly the
    approach used for ``dm_messages``. A re-seen notification only bumps ``last_seen_at``.
    """

    def ensure_table(self) -> None:
        """Create the notifications table when the bot runs against a standalone DB."""
        cursor = self._conn.cursor()
        create_notifications_tables(cursor)
        create_notifications_indexes(cursor)
        self._conn.commit()

    @staticmethod
    def _stable_content(body: Optional[str], relative_time: Optional[str]) -> str:
        """Language/time-independent core of a notification body, used in the dedup key.

        A scanned body carries VOLATILE bits that changed the hash on every re-scan and re-inserted
        the same notification (device: one follower produced 10 rows): the relative age ("4h"/"5 h"/
        "1w"/"6 j"), the action-button label ("Follow back"/"Suivre en retour") and the whole phrase
        in the app's CURRENT language ("started following you" vs "a commencé à vous suivre"). The
        only stable part is the QUOTED content after the ":" — our comment/post text, identical
        whatever the scan's language or time. So:
          - follows / post-likes (no ":") -> "" -> they dedup on (type, actor) alone; a follow is a
            follow, we must not count the same person again just because the age string changed;
          - comment-likes / mentions / replies -> the quoted comment preview -> distinct comments
            stay distinct, but the same comment re-scanned later collapses."""
        if not body:
            return ""
        core = body.split(":", 1)[1] if ":" in body else ""
        core = " ".join(core.split())
        if relative_time:
            rt = " ".join(str(relative_time).split())
            if rt and core.endswith(rt):
                core = core[: -len(rt)]
        return core.strip().lower()

    @staticmethod
    def content_hash(platform: str, account_id: int, ntype: Optional[str],
                     actor: Optional[str], body: Optional[str],
                     relative_time: Optional[str] = None) -> str:
        """Stable identity for a notification (no server id exists). Built only from time/language-
        independent parts (see ``_stable_content``) so the same notification is not re-inserted on
        every re-scan."""
        core = NotificationRepository._stable_content(body, relative_time)
        raw = f"{platform}\n{account_id}\n{ntype or ''}\n{actor or ''}\n{core}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def latest_seen_at(self, platform: str, account_id: int) -> Optional[str]:
        """When the account's last scan saw a notification (`last_seen_at`, UTC text), or None.

        Each scan bumps `last_seen_at` of every row it reads, so the most recent one is the time
        of the last scan that read anything: what « not read yet » is measured against."""
        row = self.query_one(
            "SELECT MAX(last_seen_at) AS last_seen FROM notifications WHERE platform = ? AND account_id = ?",
            (platform, account_id),
        )
        return row["last_seen"] if row is not None and row["last_seen"] else None

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
        chash = self.content_hash(platform, account_id, ntype, actor, body, relative_time)
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
