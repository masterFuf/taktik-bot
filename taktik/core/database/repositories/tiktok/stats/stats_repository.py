"""TikTok daily stats repository methods.

Reads and writes go through the unified `daily_stats_unified` table
(platform='tiktok'); the legacy `tiktok_daily_stats` table is dropped (Vague B).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger


class TikTokStatsRepositoryMixin:
    """SQL owner for TikTok daily stats (unified `daily_stats_unified`)."""

    def get_or_create_daily_stats(self, account_id: int, date: Optional[str] = None) -> Dict[str, Any]:
        """Get or create daily stats"""
        target_date = date or datetime.now().strftime('%Y-%m-%d')

        row = self.query_one(
            "SELECT * FROM daily_stats_unified WHERE platform = 'tiktok' AND account_id = ? AND date = ?",
            (account_id, target_date)
        )

        if not row:
            self.execute(
                "INSERT OR IGNORE INTO daily_stats_unified (platform, account_id, date) VALUES ('tiktok', ?, ?)",
                (account_id, target_date)
            )
            row = self.query_one(
                "SELECT * FROM daily_stats_unified WHERE platform = 'tiktok' AND account_id = ? AND date = ?",
                (account_id, target_date)
            )

        return dict(row) if row else {}

    def increment_stat(self, account_id: int, stat_name: str, amount: int = 1) -> bool:
        """Increment a stat"""
        date = datetime.now().strftime('%Y-%m-%d')
        self.get_or_create_daily_stats(account_id, date)

        valid_stats = [
            'total_likes', 'total_follows', 'total_favorites', 'total_comments',
            'total_shares', 'total_profile_visits', 'total_posts_watched',
            'total_sessions', 'completed_sessions', 'failed_sessions', 'total_duration_seconds'
        ]

        if stat_name not in valid_stats:
            return False

        cursor = self.execute(
            f"""UPDATE daily_stats_unified
                SET {stat_name} = {stat_name} + ?, updated_at = datetime('now')
                WHERE platform = 'tiktok' AND account_id = ? AND date = ?""",
            (amount, account_id, date)
        )
        return cursor.rowcount > 0

    def increment_interaction_stat(self, account_id: int, interaction_type: str) -> bool:
        """Increment the daily stat matching a TikTok interaction type."""
        column_map = {
            'LIKE': 'total_likes',
            'FOLLOW': 'total_follows',
            'FAVORITE': 'total_favorites',
            'COMMENT': 'total_comments',
            'SHARE': 'total_shares',
            'PROFILE_VISIT': 'total_profile_visits',
            'POST_WATCH': 'total_posts_watched',
        }

        column = column_map.get(interaction_type.upper())
        if not column:
            return False
        return self.increment_stat(account_id, column)

    def get_daily_stats(self, account_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Get TikTok daily stats for an account (ORM-first, fallback raw)."""
        rows = self.query_orm_first(
            """
            SELECT * FROM daily_stats_unified
            WHERE platform = 'tiktok' AND account_id = ? AND date >= date('now', '-' || ? || ' days')
            ORDER BY date DESC
            """,
            (account_id, days),
        )
        return [dict(row) for row in rows]
