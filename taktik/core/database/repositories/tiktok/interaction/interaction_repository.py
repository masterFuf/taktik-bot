"""TikTok interaction repository methods."""

from typing import Any, Dict, List, Optional

from loguru import logger


class TikTokInteractionRepositoryMixin:
    """SQL owner for TikTok interactions.

    Reads go through the unified `interactions` table (platform='tiktok'); writes
    still mirror the legacy `tiktok_interaction_history` table (Vague B Phase A).
    """

    def record_interaction(
        self,
        account_id: int,
        profile_id: int,
        interaction_type: str,
        success: bool = True,
        content: Optional[str] = None,
        video_id: Optional[str] = None,
        session_id: Optional[int] = None
    ) -> Optional[int]:
        """Record an interaction"""
        try:
            cursor = self.execute(
                """INSERT INTO tiktok_interaction_history
                   (session_id, account_id, profile_id, interaction_type, success, content, video_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, account_id, profile_id, interaction_type,
                 1 if success else 0, content, video_id)
            )
            rowid = cursor.lastrowid
            # Dual-write into the unified `interactions` table (Vague B Phase A).
            # legacy_id = the legacy row id so the boot backfill dedups (no dup).
            try:
                self.execute(
                    """INSERT OR IGNORE INTO interactions
                       (platform, legacy_id, session_id, account_id, profile_id, interaction_type, success, content, video_id, interaction_time)
                       VALUES ('tiktok', ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (rowid, session_id, account_id, profile_id, interaction_type,
                     1 if success else 0, content, video_id),
                )
            except Exception as exc:
                logger.debug(f"interactions mirror (tiktok) failed: {exc}")
            return rowid
        except Exception as e:
            logger.error(f"Error recording TikTok interaction: {e}")
            return None

    def record_interaction_for_username(
        self,
        account_id: int,
        target_username: str,
        interaction_type: str,
        success: bool = True,
        content: Optional[str] = None,
        video_id: Optional[str] = None,
        session_id: Optional[int] = None,
    ) -> bool:
        """Record a TikTok interaction and update daily stats."""
        try:
            profile_id, _ = self.get_or_create_profile(target_username)
            interaction_id = self.record_interaction(
                account_id=account_id,
                profile_id=profile_id,
                interaction_type=interaction_type.upper(),
                success=success,
                content=content,
                video_id=video_id,
                session_id=session_id,
            )
            if interaction_id is None:
                return False

            self.increment_interaction_stat(account_id, interaction_type)
            logger.debug(f"Recorded TikTok {interaction_type} on @{target_username}")
            return True
        except Exception as e:
            logger.error(f"Error recording TikTok interaction: {e}")
            return False

    def check_recent_interaction(self, target_username: str, account_id: int, hours: int = 168) -> bool:
        """Check if there was a recent TikTok interaction with a profile."""
        profile = self.find_profile_by_username(target_username)
        if not profile:
            return False

        row = self.query_one(
            """
            SELECT COUNT(*) as count FROM interactions
            WHERE platform = 'tiktok'
            AND account_id = ?
            AND profile_id = ?
            AND interaction_time >= datetime('now', '-' || ? || ' hours')
            """,
            (account_id, profile['profile_id'], hours),
        )
        return (row['count'] if row else 0) > 0

    def get_interactions(self, account_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent TikTok interactions for an account."""
        rows = self.query(
            """
            SELECT ih.legacy_id AS id, ih.session_id, ih.account_id, ih.profile_id,
                   ih.interaction_type, ih.interaction_time, ih.success, ih.content, ih.video_id,
                   tp.username as target_username
            FROM interactions ih
            JOIN tiktok_profiles tp ON ih.profile_id = tp.profile_id
            WHERE ih.platform = 'tiktok' AND ih.account_id = ?
            ORDER BY ih.interaction_time DESC
            LIMIT ?
            """,
            (account_id, limit),
        )
        return [dict(row) for row in rows]

    def has_interaction(self, account_id: int, target_username: str, hours: int = 168) -> bool:
        """Check if an account already interacted with a TikTok profile."""
        return self.check_recent_interaction(target_username, account_id, hours)

    def count_interactions_for_target(self, account_id: int, target_username: str, hours: int = 168) -> int:
        """Count unique interacted profiles for a target's follower workflow."""
        row = self.query_one(
            """
            SELECT COUNT(DISTINCT ih.profile_id) as count
            FROM interactions ih
            JOIN sessions_unified ts ON ts.legacy_session_id = ih.session_id AND ts.platform = 'tiktok'
            WHERE ih.platform = 'tiktok'
            AND ih.account_id = ?
            AND ts.target = ?
            AND ih.interaction_time >= datetime('now', '-' || ? || ' hours')
            """,
            (account_id, target_username, hours),
        )
        return row['count'] if row else 0

    def get_interactions_by_session(self, session_id: int) -> List[Dict[str, Any]]:
        """Get interactions by session"""
        rows = self.query(
            """SELECT legacy_id AS id, session_id, account_id, profile_id,
                      interaction_type, interaction_time, success, content, video_id
               FROM interactions WHERE platform = 'tiktok' AND session_id = ? ORDER BY interaction_time DESC""",
            (session_id,)
        )
        return [{**dict(r), 'success': bool(dict(r).get('success', 0))} for r in rows]
