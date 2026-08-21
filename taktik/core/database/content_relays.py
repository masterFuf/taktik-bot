"""Database facade for the content relay journal.

Owns every read and write of `content_relays`, so the relay task can stay a sequence of
screen gestures and never carry SQL of its own.

Two questions only. Before acting: "have we already handled this story for this pair of
accounts?" — `already_handled`. After acting: "here is what happened" — `record`. Both are
keyed on the same signature, so a verdict written once is the verdict the next pass reads.

`record` upserts rather than inserts: the unique index makes a second write on the same
signature a conflict, and a relay that crashed the app on its second pass would be a worse
outcome than a duplicated attempt. The stored status is the LATEST one — a story that was
'unavailable' at 9am and relayed at noon reads as relayed.

Never raises. A journal that cannot be written must not take the run down with it; the caller
gets a falsy answer and the relay simply declines to act, which is the safe direction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

log = logger.bind(module="database-content-relays")

#: What a relay attempt can conclude. 'unavailable' is the interesting one — it means the app
#: did not offer the re-share affordance, which is a product answer rather than a bug.
STATUSES = ("relayed", "skipped", "unavailable", "failed")


class ContentRelayService:
    """Read/write side of the relay journal."""

    @staticmethod
    def _db():
        from taktik.core.database.local.service import get_local_database

        return get_local_database()

    @staticmethod
    def already_handled(
        *,
        account_id: Optional[int],
        source_username: str,
        media_signature: str,
        platform: str = "instagram",
    ) -> bool:
        """Whether this exact story already has a verdict for this pair of accounts.

        Any verdict counts, not just a successful relay: re-attempting a story the app
        refused would burn a device pass on every tick for as long as the story is up.
        """
        if not source_username or not media_signature:
            return False
        try:
            conn = ContentRelayService._db()._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM content_relays
                WHERE account_id IS ? AND platform = ?
                  AND source_username = ? AND media_signature = ?
                LIMIT 1
                """,
                (account_id, platform, source_username, media_signature),
            )
            return cursor.fetchone() is not None
        except Exception as exc:
            # Answering "yes, already handled" on a read failure would silently stop the relay
            # forever; answering "no" costs at worst one duplicate attempt.
            log.debug(f"Could not read the relay journal: {exc}")
            return False

    @staticmethod
    def record(
        *,
        account_id: Optional[int],
        source_username: str,
        media_signature: str,
        status: str,
        reason: Optional[str] = None,
        kind: str = "story",
        platform: str = "instagram",
    ) -> bool:
        """Write the outcome of one relay attempt. Returns whether it was stored."""
        if status not in STATUSES:
            log.debug(f"Refusing to store an unknown relay status: {status!r}")
            return False
        if not source_username or not media_signature:
            return False
        try:
            conn = ContentRelayService._db()._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO content_relays
                    (account_id, platform, source_username, media_signature, kind, status, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, platform, source_username, media_signature) DO UPDATE SET
                    status = excluded.status,
                    reason = excluded.reason,
                    updated_at = datetime('now')
                """,
                (account_id, platform, source_username, media_signature, kind, status, reason),
            )
            conn.commit()
            return True
        except Exception as exc:
            log.debug(f"Could not record a relay outcome: {exc}")
            return False

    @staticmethod
    def recent(
        *,
        account_id: Optional[int] = None,
        limit: int = 50,
        platform: str = "instagram",
    ) -> List[Dict[str, Any]]:
        """The journal as a page reads it: newest first, optionally for one account."""
        try:
            conn = ContentRelayService._db()._get_connection()
            cursor = conn.cursor()
            if account_id is None:
                cursor.execute(
                    """
                    SELECT id, account_id, source_username, media_signature, kind,
                           status, reason, created_at, updated_at
                    FROM content_relays
                    WHERE platform = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (platform, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, account_id, source_username, media_signature, kind,
                           status, reason, created_at, updated_at
                    FROM content_relays
                    WHERE platform = ? AND account_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (platform, account_id, limit),
                )
            columns = [c[0] for c in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as exc:
            log.debug(f"Could not read the relay journal: {exc}")
            return []


__all__ = ["ContentRelayService", "STATUSES"]
