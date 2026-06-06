"""
Interaction Repository - Manages filtered_profiles and Instagram interactions.

Reads and writes go through the unified `interactions` table
(platform='instagram'); the legacy `interaction_history` table is dropped (Vague B).
"""

from typing import Dict, List, Optional, Tuple, Any
from loguru import logger
from ..._base.base_repository import BaseRepository


class InteractionRepository(BaseRepository):
    """Repository for interactions and filtered profiles"""
    
    # ============================================
    # INTERACTIONS
    # ============================================
    
    def record(
        self,
        account_id: int,
        profile_id: int,
        interaction_type: str,
        success: bool = True,
        content: Optional[str] = None,
        session_id: Optional[int] = None
    ) -> Optional[int]:
        """Record a new interaction"""
        try:
            # Vague B Phase C: write directly to the unified `interactions` table
            # (legacy interaction_history dropped). sync_id generated for Turso.
            cursor = self.execute(
                """INSERT INTO interactions
                   (platform, sync_id, session_id, account_id, profile_id, interaction_type, success, content, interaction_time, created_at)
                   VALUES ('instagram', lower(hex(randomblob(16))), ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (session_id, account_id, profile_id, interaction_type.upper(), 1 if success else 0, content)
            )
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error recording interaction: {e}")
            return None
    
    def has_recent_interaction(
        self, 
        account_id: int, 
        profile_id: int, 
        days: int = 7
    ) -> bool:
        """Check if there was a recent interaction with a profile"""
        row = self.query_one(
            """SELECT COUNT(*) as count FROM interactions
               WHERE platform = 'instagram' AND account_id = ? AND profile_id = ?
               AND interaction_time >= datetime('now', '-' || ? || ' days')""",
            (account_id, profile_id, days)
        )
        return (row['count'] if row else 0) > 0
    
    def find_by_account(self, account_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get interactions by account"""
        rows = self.query(
            """SELECT ih.id, ih.session_id, ih.account_id, ih.profile_id,
                      ih.interaction_type, ih.interaction_time, ih.success, ih.content,
                      ip.username as target_username
               FROM interactions ih
               JOIN instagram_profiles ip ON ih.profile_id = ip.profile_id
               WHERE ih.platform = 'instagram' AND ih.account_id = ?
               ORDER BY ih.interaction_time DESC
               LIMIT ?""",
            (account_id, limit)
        )
        return [self._map_interaction_row(row) for row in rows]
    
    def find_by_session(self, session_id: int) -> List[Dict[str, Any]]:
        """Get interactions by session"""
        rows = self.query(
            """SELECT ih.id, ih.session_id, ih.account_id, ih.profile_id,
                      ih.interaction_type, ih.interaction_time, ih.success, ih.content,
                      ip.username as target_username
               FROM interactions ih
               JOIN instagram_profiles ip ON ih.profile_id = ip.profile_id
               WHERE ih.platform = 'instagram' AND ih.session_id = ?
               ORDER BY ih.interaction_time DESC""",
            (session_id,)
        )
        return [self._map_interaction_row(row) for row in rows]
    
    def count_by_type(
        self, 
        account_id: int, 
        interaction_type: str, 
        days: Optional[int] = None
    ) -> int:
        """Count interactions by type for an account"""
        if days:
            row = self.query_one(
                """SELECT COUNT(*) as count FROM interactions
                   WHERE platform = 'instagram' AND account_id = ? AND interaction_type = ?
                   AND interaction_time >= datetime('now', '-' || ? || ' days')""",
                (account_id, interaction_type.upper(), days)
            )
        else:
            row = self.query_one(
                "SELECT COUNT(*) as count FROM interactions WHERE platform = 'instagram' AND account_id = ? AND interaction_type = ?",
                (account_id, interaction_type.upper())
            )
        return row['count'] if row else 0
    
    def get_session_stats(self, session_id: int) -> Dict[str, int]:
        """Get aggregated interaction stats for a session."""
        row = self.query_one(
            """
            SELECT
                COUNT(*) as total_interactions,
                SUM(CASE WHEN interaction_type = 'LIKE' THEN 1 ELSE 0 END) as total_likes,
                SUM(CASE WHEN interaction_type = 'FOLLOW' THEN 1 ELSE 0 END) as total_follows,
                SUM(CASE WHEN interaction_type = 'UNFOLLOW' THEN 1 ELSE 0 END) as total_unfollows,
                SUM(CASE WHEN interaction_type = 'COMMENT' THEN 1 ELSE 0 END) as total_comments,
                SUM(CASE WHEN interaction_type = 'STORY_WATCH' THEN 1 ELSE 0 END) as total_story_views,
                SUM(CASE WHEN interaction_type = 'STORY_LIKE' THEN 1 ELSE 0 END) as total_story_likes,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_interactions
            FROM interactions
            WHERE platform = 'instagram' AND session_id = ?
            """,
            (session_id,)
        )
        if not row:
            return {
                'total_interactions': 0,
                'total_likes': 0,
                'total_follows': 0,
                'total_unfollows': 0,
                'total_comments': 0,
                'total_story_views': 0,
                'total_story_likes': 0,
                'successful_interactions': 0,
            }
        return {
            'total_interactions': row['total_interactions'] or 0,
            'total_likes': row['total_likes'] or 0,
            'total_follows': row['total_follows'] or 0,
            'total_unfollows': row['total_unfollows'] or 0,
            'total_comments': row['total_comments'] or 0,
            'total_story_views': row['total_story_views'] or 0,
            'total_story_likes': row['total_story_likes'] or 0,
            'successful_interactions': row['successful_interactions'] or 0,
        }
    
    # ============================================
    # FILTERED PROFILES
    # ============================================
    
    def record_filtered(
        self,
        account_id: int,
        profile_id: int,
        username: str,
        reason: str,
        source_type: str = 'GENERAL',
        source_name: str = 'unknown',
        session_id: Optional[int] = None
    ) -> bool:
        """Record a filtered profile (unified filtered_profiles, platform='instagram')."""
        try:
            # Generate a Turso sync_id on first insert; ON CONFLICT preserves it (and the
            # id) when re-filtering the same target.
            self.execute(
                """INSERT INTO filtered_profiles
                       (platform, profile_id, account_id, username, reason, source_type, source_name, session_id, sync_id)
                   VALUES ('instagram', ?, ?, ?, ?, ?, ?, ?, lower(hex(randomblob(16))))
                   ON CONFLICT(platform, profile_id, account_id) DO UPDATE SET
                       username = excluded.username,
                       reason = excluded.reason,
                       source_type = excluded.source_type,
                       source_name = excluded.source_name,
                       session_id = excluded.session_id,
                       filtered_at = datetime('now')""",
                (profile_id, account_id, username, reason, source_type, source_name, session_id)
            )
            return True
        except Exception as e:
            logger.error(f"Error recording filtered profile: {e}")
            return False

    def is_filtered(self, username: str, account_id: int) -> bool:
        """Check if a profile is filtered for an account"""
        row = self.query_one(
            "SELECT COUNT(*) as count FROM filtered_profiles WHERE platform = 'instagram' AND username = ? AND account_id = ?",
            (username, account_id)
        )
        return (row['count'] if row else 0) > 0

    def get_filtered_usernames(self, usernames: List[str], account_id: int) -> List[str]:
        """Check multiple profiles at once (batch)"""
        if not usernames:
            return []

        placeholders = ','.join('?' * len(usernames))
        rows = self.query(
            f"SELECT username FROM filtered_profiles WHERE platform = 'instagram' AND account_id = ? AND username IN ({placeholders})",
            (account_id, *usernames)
        )
        return [row['username'] for row in rows]

    def get_filtered_profiles(self, account_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get filtered profiles for an account"""
        rows = self.query(
            "SELECT * FROM filtered_profiles WHERE platform = 'instagram' AND account_id = ? ORDER BY filtered_at DESC LIMIT ?",
            (account_id, limit)
        )
        return self.rows_to_dicts(rows)

    def remove_filtered(self, username: str, account_id: int) -> bool:
        """Remove a profile from filtered list"""
        cursor = self.execute(
            "DELETE FROM filtered_profiles WHERE platform = 'instagram' AND username = ? AND account_id = ?",
            (username, account_id)
        )
        return cursor.rowcount > 0

    def count_filtered(self, account_id: int) -> int:
        """Count filtered profiles for an account"""
        row = self.query_one(
            "SELECT COUNT(*) as count FROM filtered_profiles WHERE platform = 'instagram' AND account_id = ?",
            (account_id,)
        )
        return row['count'] if row else 0
    
    def _map_interaction_row(self, row) -> Dict[str, Any]:
        """Map database row to dict"""
        row_dict = dict(row)
        return {
            **row_dict,
            'success': bool(row_dict.get('success', 0))
        }
