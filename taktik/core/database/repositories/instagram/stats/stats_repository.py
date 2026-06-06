"""
Stats Repository - Manages Instagram daily stats.

Reads and writes go through the unified `daily_stats_unified` table
(platform='instagram'); the legacy `daily_stats` table is dropped (Vague B).
"""

from datetime import datetime
from typing import Any, Dict, List

from loguru import logger

from ..._base.base_repository import BaseRepository


class StatsRepository(BaseRepository):
    """Repository for Instagram daily stats and account analytics."""

    _INTERACTION_COLUMN_MAP = {
        'LIKE': 'total_likes',
        'FOLLOW': 'total_follows',
        'UNFOLLOW': 'total_unfollows',
        'COMMENT': 'total_comments',
        'STORY_WATCH': 'total_story_views',
        'STORY_LIKE': 'total_story_likes',
        'PROFILE_VISIT': 'total_profile_visits',
    }

    def increment_interaction(self, account_id: int, interaction_type: str) -> bool:
        """Increment the matching daily_stats counter for an interaction."""
        column = self._INTERACTION_COLUMN_MAP.get(interaction_type.upper())
        if not column:
            return False

        today = datetime.now().strftime('%Y-%m-%d')
        self.execute(
            f"""
            INSERT INTO daily_stats_unified (platform, account_id, date, {column})
            VALUES ('instagram', ?, ?, 1)
            ON CONFLICT(platform, account_id, date) DO UPDATE SET
                {column} = {column} + 1,
                updated_at = datetime('now')
            """,
            (account_id, today),
        )
        return True

    def increment_session_count(self, account_id: int) -> None:
        """Increment the number of sessions started today."""
        today = datetime.now().strftime('%Y-%m-%d')
        self.execute(
            """
            INSERT INTO daily_stats_unified (platform, account_id, date, total_sessions)
            VALUES ('instagram', ?, ?, 1)
            ON CONFLICT(platform, account_id, date) DO UPDATE SET
                total_sessions = total_sessions + 1,
                updated_at = datetime('now')
            """,
            (account_id, today),
        )

    def record_session_completion(self, account_id: int, status: str, duration: int) -> None:
        """Increment completion/failure counters and accumulate duration."""
        today = datetime.now().strftime('%Y-%m-%d')
        column = 'completed_sessions' if status == 'COMPLETED' else 'failed_sessions'
        self.execute(
            f"""
            INSERT INTO daily_stats_unified (platform, account_id, date, {column}, total_duration_seconds)
            VALUES ('instagram', ?, ?, 1, ?)
            ON CONFLICT(platform, account_id, date) DO UPDATE SET
                {column} = {column} + 1,
                total_duration_seconds = total_duration_seconds + ?,
                updated_at = datetime('now')
            """,
            (account_id, today, duration, duration),
        )

    def find_unsynced(self) -> List[Dict[str, Any]]:
        """Return daily stats rows that still need API sync."""
        rows = self.query(
            "SELECT * FROM daily_stats_unified WHERE platform = 'instagram' AND synced_to_api = 0 ORDER BY date DESC, id DESC"
        )
        return self.rows_to_dicts(rows)

    def mark_as_synced(self, stat_ids: List[int]) -> bool:
        """Mark daily stats rows as synced."""
        if not stat_ids:
            return True

        placeholders = ','.join('?' * len(stat_ids))
        cursor = self.execute(
            f"""
            UPDATE daily_stats_unified
            SET synced_to_api = 1, synced_at = datetime('now')
            WHERE id IN ({placeholders})
            """,
            tuple(stat_ids),
        )
        return cursor.rowcount > 0

    def get_account_stats(self, account_id: int, days: int = 7) -> Dict[str, Any]:
        """Return aggregated daily stats for an account over the last N days."""
        row = self.query_one(
            """
            SELECT
                COALESCE(SUM(total_sessions), 0) as total_sessions,
                COALESCE(SUM(total_likes), 0) as total_likes,
                COALESCE(SUM(total_follows), 0) as total_follows,
                COALESCE(SUM(total_unfollows), 0) as total_unfollows,
                COALESCE(SUM(total_comments), 0) as total_comments,
                COALESCE(SUM(total_story_views), 0) as total_story_views,
                COALESCE(SUM(total_story_likes), 0) as total_story_likes,
                COALESCE(SUM(total_profile_visits), 0) as total_profile_visits,
                COALESCE(SUM(total_duration_seconds), 0) as total_duration,
                COALESCE(SUM(completed_sessions), 0) as completed_sessions,
                COALESCE(SUM(failed_sessions), 0) as failed_sessions
            FROM daily_stats_unified
            WHERE platform = 'instagram' AND account_id = ?
            AND date >= date('now', '-' || ? || ' days')
            """,
            (account_id, days),
        )
        return dict(row) if row else {}
