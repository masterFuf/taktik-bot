"""Database facade for cross-platform notifications bookkeeping.

Coordinator: opens one connection and orchestrates the notifications repository.
SECURITY: never logs notification body — only counts / usernames / types (AGENTS.md).
Source of truth is the Bot; Electron reads this table (read-only) and Turso syncs it.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List, Optional

from loguru import logger

from taktik.core.database.local.paths import get_default_database_path
from taktik.core.database.repositories.notifications import NotificationRepository


class NotificationService:
    """Persist scanned notifications (dedup across re-scans), cross-platform."""

    @staticmethod
    def _open() -> Optional[sqlite3.Connection]:
        db_path = get_default_database_path()
        if not os.path.exists(db_path):
            logger.warning(f"Database not found at {db_path}")
            return None
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def record_notifications(
        *,
        platform: str,
        account_id: int,
        items: List[Dict[str, Any]],
    ) -> List[bool]:
        """Persist scanned notification ``items``; return ``is_new`` per item (same order).

        ``items`` are the scan dicts ``{type, username, time, text, label, has_action, ...}``.
        Best-effort: a missing DB or a bad item never raises into the scan. Returns a flag
        list aligned with ``items`` (True = first time seen). NEVER logs the body.
        """
        if not items:
            return []
        conn = NotificationService._open()
        if conn is None:
            return [False] * len(items)

        flags: List[bool] = []
        try:
            repo = NotificationRepository(conn)
            repo.ensure_table()
            for item in items:
                try:
                    is_new = repo.record(
                        platform=platform,
                        account_id=account_id,
                        actor_username=item.get("username"),
                        actor_profile_id=item.get("actor_profile_id"),
                        ntype=item.get("type"),
                        raw_category=item.get("raw_category") or item.get("type"),
                        label=item.get("label"),
                        body=item.get("text"),
                        relative_time=item.get("time"),
                        has_action=bool(item.get("has_action")),
                        attributed=bool(item.get("attributed")),
                        attribution_type=item.get("attribution_type"),
                        attribution_at=item.get("attribution_at"),
                    )
                except Exception as exc:
                    logger.warning(f"Error recording one notification: {exc}")
                    is_new = False
                flags.append(is_new)
            new_count = sum(1 for flag in flags if flag)
            logger.info(
                f"Recorded {len(items)} notifications ({new_count} new) "
                f"for account {account_id} [{platform}]"
            )
            return flags
        except Exception as exc:
            logger.warning(f"Error recording notifications: {exc}")
            flags.extend([False] * (len(items) - len(flags)))
            return flags
        finally:
            conn.close()


__all__ = ["NotificationService"]
