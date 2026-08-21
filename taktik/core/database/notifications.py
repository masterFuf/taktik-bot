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
from taktik.core.database.repositories.notifications import (
    NotificationActionRepository,
    NotificationRepository,
)


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
    def known_content_hashes(platform: str, account_id: int) -> set:
        """The set of STABLE content_hashes already recorded for this account — for the scan's
        early-stop. Preloaded once so the scan recognises already-seen notifications in memory (no
        per-row DB hit) and stops scrolling once it reaches known territory.

        We RECOMPUTE the stable hash from each stored row's (type, actor, body, relative_time)
        rather than reading the ``content_hash`` column: rows recorded before the stable-hash change
        carry a body-based hash that a re-scan will never reproduce, so reading the column would
        make the early-stop blind to everything older. Recomputing here yields exactly the hash a
        fresh scan computes, so both old and new rows are recognised — no data migration needed.
        Best-effort: returns an empty set on any error (=> the scan reads fully, as before)."""
        conn = NotificationService._open()
        if conn is None:
            return set()
        try:
            rows = conn.execute(
                "SELECT type, actor_username, body, relative_time FROM notifications "
                "WHERE platform = ? AND account_id = ?",
                (platform, account_id),
            ).fetchall()
            out = set()
            for row in rows:
                actor = (row["actor_username"] or "").strip().lower() or None
                out.add(NotificationRepository.content_hash(
                    platform, account_id, row["type"], actor, row["body"], row["relative_time"]))
            return out
        except Exception as exc:
            logger.warning(f"Could not load known notification hashes: {exc}")
            return set()
        finally:
            conn.close()

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

    # ------------------------------------------------------------------
    # Actions WE took on notifications (audit + idempotence — autopilot spec)
    # ------------------------------------------------------------------

    @staticmethod
    def identity_hash(platform: str, account_id: int,
                      identity: Optional[Dict[str, Any]]) -> Optional[str]:
        """The notification's stable content_hash from a caller-supplied identity
        ``{ntype, actor, text, time}`` (the batch entries carry it), or None."""
        if not identity:
            return None
        actor = (identity.get("actor") or "").strip().lower() or None
        ntype = identity.get("ntype")
        if not (actor or ntype):
            return None
        return NotificationRepository.content_hash(
            platform, account_id, ntype, actor, identity.get("text"), identity.get("time"))

    @staticmethod
    def record_action(
        *,
        platform: str,
        account_id: int,
        action: str,
        actor_username: Optional[str] = None,
        content_hash: Optional[str] = None,
        source: str = "manual",
        success: bool = True,
    ) -> None:
        """Persist one executed action (best-effort: never raises into the action flow)."""
        conn = NotificationService._open()
        if conn is None:
            return
        try:
            NotificationActionRepository(conn).record(
                platform=platform, account_id=account_id, action=action,
                actor_username=actor_username, content_hash=content_hash,
                source=source, success=success,
            )
            conn.commit()
        except Exception as exc:
            logger.warning(f"Could not record notification action '{action}': {exc}")
        finally:
            conn.close()

    @staticmethod
    def actioned_hashes(platform: str, account_id: int, action: str) -> set:
        """content_hashes on which ``action`` already succeeded — for the batch's
        idempotent skip. Best-effort: empty set on any error (=> nothing is skipped)."""
        conn = NotificationService._open()
        if conn is None:
            return set()
        try:
            return NotificationActionRepository(conn).actioned_hashes(
                platform, account_id, action)
        except Exception as exc:
            logger.warning(f"Could not load actioned hashes: {exc}")
            return set()
        finally:
            conn.close()


__all__ = ["NotificationService"]
