"""The life of a scraping run: created, progressing, then finished one way or another.

Owns `scraping_sessions` — what was scraped, from which source, how long it took, and how it
ended. The terminal states are part of the contract with the desktop app: COMPLETED, ERROR,
CANCELLED (the operator stopped it) and INTERRUPTED (the app died and nobody closed the row).

Two things here are easy to get wrong and are therefore kept in one place:

`sync_id` is generated at INSERT. A NULL one makes the Turso push re-insert the row on every
cycle, because NULL is distinct from NULL on the primary key — the row would multiply
forever instead of updating.

Durations are computed as a UTC delta. Timestamps are stored by SQLite's `datetime('now')`,
which is UTC; reading them as local time added the machine's offset to every duration.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from ..._base.base_repository import BaseRepository


# Columns an update may touch. Anything else is ignored rather than injected: the update is
# built by concatenation, so the allowed names must come from here and never from the caller.
_UPDATABLE_COLUMNS = (
    "total_scraped",
    "csv_path",
    "end_time",
    "duration_seconds",
    "status",
    "error_message",
)


def parse_stored_utc(value: Any, default: datetime) -> datetime:
    """Read a stored timestamp as aware UTC.

    Stored timestamps come from SQLite's `datetime('now')`, which is UTC. A naive string is
    therefore treated as UTC, not local — reading it as local time offsets every duration by
    the machine's timezone.
    """
    if not value:
        return default
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return default
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class ScrapingSessionRepository(BaseRepository):
    """Scraping runs and their outcome."""

    def create(self, scraping_type: str, source_type: str, source_name: str,
               max_profiles: int = 500, export_csv: bool = False,
               save_to_db: bool = True, account_id: Optional[int] = None,
               config: Optional[Dict] = None) -> Optional[int]:
        """Open a session and return its id, or None when it could not be created."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO scraping_sessions
                (account_id, scraping_type, source_type, source_name, max_profiles,
                 export_csv, save_to_db, config_used, sync_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, lower(hex(randomblob(16))))
                """,
                (
                    account_id,
                    scraping_type,
                    source_type,
                    source_name,
                    max_profiles,
                    1 if export_csv else 0,
                    1 if save_to_db else 0,
                    json.dumps(self._redact_sensitive(config)) if config else None,
                ),
            )
            self.conn.commit()
            scraping_id = cursor.lastrowid
            logger.info(
                f"Created scraping session {scraping_id}: {scraping_type} "
                f"from {source_type}:{source_name}"
            )
            return scraping_id
        except Exception as exc:
            logger.error(f"Error creating scraping session: {exc}")
            return None

    def update(self, scraping_id: int, **kwargs) -> bool:
        """Update the columns named in `_UPDATABLE_COLUMNS`; ignore anything else."""
        try:
            updates, values = [], []
            for column in _UPDATABLE_COLUMNS:
                if column in kwargs:
                    updates.append(f"{column} = ?")
                    values.append(kwargs[column])
            if not updates:
                return True

            values.append(scraping_id)
            cursor = self.conn.cursor()
            cursor.execute(
                f"UPDATE scraping_sessions SET {', '.join(updates)} WHERE scraping_id = ?",
                values,
            )
            self.conn.commit()
            return True
        except Exception as exc:
            logger.error(f"Error updating scraping session {scraping_id}: {exc}")
            return False

    def update_count(self, scraping_id: int, total_scraped: int) -> bool:
        """Save progress mid-run, so a crash still leaves a truthful count behind."""
        try:
            self.conn.execute(
                "UPDATE scraping_sessions SET total_scraped = ? WHERE scraping_id = ?",
                (total_scraped, scraping_id),
            )
            self.conn.commit()
            return True
        except Exception as exc:
            logger.debug(f"Error updating scraping session count: {exc}")
            return False

    def _finish(self, scraping_id: int, total_scraped: int, status: str,
                csv_path: Optional[str] = None,
                error_message: Optional[str] = None) -> bool:
        """Close a session with its duration measured from the stored UTC start."""
        session = self.get(scraping_id)
        if not session:
            return False

        end_time = datetime.now(timezone.utc)
        start_time = parse_stored_utc(session.get("start_time"), end_time)
        duration = max(0, int((end_time - start_time).total_seconds()))

        return self.update(
            scraping_id,
            total_scraped=total_scraped,
            csv_path=csv_path,
            end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
            duration_seconds=duration,
            status=status,
            error_message=error_message,
        )

    def complete(self, scraping_id: int, total_scraped: int,
                 csv_path: Optional[str] = None,
                 error_message: Optional[str] = None) -> bool:
        """Finish a run: COMPLETED, or ERROR when it carries a message."""
        return self._finish(
            scraping_id, total_scraped,
            status="COMPLETED" if not error_message else "ERROR",
            csv_path=csv_path, error_message=error_message,
        )

    def cancel(self, scraping_id: int, total_scraped: int) -> bool:
        """The operator stopped it — a distinct outcome from a failure."""
        return self._finish(scraping_id, total_scraped, status="CANCELLED")

    def cleanup_orphans(self) -> int:
        """Close the sessions nobody closed, and report how many there were.

        A row still IN_PROGRESS at startup means the app died mid-run. Left alone it stays
        open forever and reads as a session still going.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE scraping_sessions
                SET status = 'INTERRUPTED',
                    end_time = datetime('now'),
                    error_message = 'Session interrupted (app closed unexpectedly)'
                WHERE status = 'IN_PROGRESS'
                """
            )
            affected = cursor.rowcount
            self.conn.commit()
            if affected > 0:
                logger.info(f"Cleaned up {affected} orphan scraping sessions")
            return affected
        except Exception as exc:
            logger.error(f"Error cleaning up orphan sessions: {exc}")
            return 0

    @staticmethod
    def _as_session(row) -> Dict[str, Any]:
        """SQLite stores the two flags as 0/1; callers expect booleans."""
        session = dict(row)
        session["export_csv"] = bool(session.get("export_csv"))
        session["save_to_db"] = bool(session.get("save_to_db"))
        return session

    def get(self, scraping_id: int) -> Optional[Dict[str, Any]]:
        row = self.query_one(
            "SELECT * FROM scraping_sessions WHERE scraping_id = ?", (scraping_id,)
        )
        return self._as_session(row) if row else None

    def list_recent(self, limit: int = 50,
                    status: Optional[str] = None) -> List[Dict[str, Any]]:
        if status:
            rows = self.query(
                """
                SELECT * FROM scraping_sessions
                WHERE status = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (status, limit),
            )
        else:
            rows = self.query(
                "SELECT * FROM scraping_sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [self._as_session(row) for row in rows]

    def stats(self, days: int = 7) -> Dict[str, Any]:
        """Aggregate over the window. COALESCE everywhere: an empty window must read as
        zeros, not as None values the caller then has to guard."""
        row = self.query_one(
            """
            SELECT
                COUNT(*) as total_sessions,
                COALESCE(SUM(total_scraped), 0) as total_profiles_scraped,
                COALESCE(SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END), 0) as completed_sessions,
                COALESCE(SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END), 0) as failed_sessions,
                COALESCE(SUM(duration_seconds), 0) as total_duration_seconds,
                COALESCE(AVG(total_scraped), 0) as avg_profiles_per_session
            FROM scraping_sessions
            WHERE created_at >= datetime('now', '-' || ? || ' days')
            """,
            (days,),
        )
        return dict(row) if row else {}


__all__ = ["ScrapingSessionRepository", "parse_stored_utc"]
