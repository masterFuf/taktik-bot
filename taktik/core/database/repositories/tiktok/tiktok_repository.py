"""
TikTok Repository - Manages tiktok_accounts, tiktok_profiles, tiktok_sessions, 
tiktok_interaction_history, tiktok_filtered_profiles, tiktok_daily_stats
"""

from typing import Dict, List, Optional, Any, Tuple

from loguru import logger

from .._base.base_repository import BaseRepository
from .session import TikTokSessionRepositoryMixin
from .stats import TikTokStatsRepositoryMixin


class TikTokRepository(TikTokStatsRepositoryMixin, TikTokSessionRepositoryMixin, BaseRepository):
    """Repository for TikTok data"""
    
    # ============================================
    # ACCOUNTS
    # ============================================
    
    def get_or_create_account(
        self,
        username: str,
        display_name: Optional[str] = None,
        is_bot: bool = True,
        user_id: Optional[int] = None,
        license_id: Optional[int] = None
    ) -> Tuple[int, bool]:
        """Get or create a TikTok account"""
        row = self.query_one(
            "SELECT account_id FROM tiktok_accounts WHERE username = ?",
            (username,)
        )
        
        if row:
            return row['account_id'], False
        
        cursor = self.execute(
            """INSERT INTO tiktok_accounts (username, display_name, is_bot, user_id, license_id)
               VALUES (?, ?, ?, ?, ?)""",
            (username, display_name, 1 if is_bot else 0, user_id, license_id)
        )
        return cursor.lastrowid, True
    
    def find_account_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Find account by username"""
        row = self.query_one(
            "SELECT * FROM tiktok_accounts WHERE username = ?",
            (username,)
        )
        if not row:
            return None
        row_dict = dict(row)
        return {**row_dict, 'is_bot': bool(row_dict.get('is_bot', 0))}
    
    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """Get all TikTok accounts"""
        rows = self.query("SELECT * FROM tiktok_accounts ORDER BY created_at DESC")
        return [{**dict(r), 'is_bot': bool(dict(r).get('is_bot', 0))} for r in rows]
    
    # ============================================
    # PROFILES
    # ============================================
    
    def get_or_create_profile(self, username: str, **kwargs) -> Tuple[int, bool]:
        """Get or create a TikTok profile"""
        row = self.query_one(
            "SELECT profile_id FROM tiktok_profiles WHERE username = ?",
            (username,)
        )
        
        if row:
            profile_id = row['profile_id']
            self._update_profile(profile_id, **kwargs)
            return profile_id, False
        
        cursor = self.execute(
            """INSERT INTO tiktok_profiles (
                username, display_name, followers_count, following_count,
                likes_count, videos_count, is_private, is_verified, biography
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                username,
                kwargs.get('display_name', ''),
                kwargs.get('followers_count', 0),
                kwargs.get('following_count', 0),
                kwargs.get('likes_count', 0),
                kwargs.get('videos_count', 0),
                1 if kwargs.get('is_private') else 0,
                1 if kwargs.get('is_verified') else 0,
                kwargs.get('biography')
            )
        )
        return cursor.lastrowid, True
    
    def _update_profile(self, profile_id: int, **kwargs) -> None:
        """Update profile with non-None values"""
        updates = []
        values = []

        for key in ('display_name', 'biography'):
            if kwargs.get(key):
                updates.append(f"{key} = COALESCE(?, {key})")
                values.append(kwargs[key])

        for key in ('followers_count', 'following_count', 'likes_count', 'videos_count'):
            value = kwargs.get(key)
            if value and value > 0:
                updates.append(f"{key} = ?")
                values.append(value)
        
        for key in ('is_private', 'is_verified'):
            if key in kwargs and kwargs[key] is not None:
                updates.append(f"{key} = COALESCE(?, {key})")
                values.append(1 if kwargs[key] else 0)
        
        if updates:
            updates.append("updated_at = datetime('now')")
            values.append(profile_id)
            self.execute(
                f"UPDATE tiktok_profiles SET {', '.join(updates)} WHERE profile_id = ?",
                tuple(values)
            )
    
    def find_profile_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Find profile by username"""
        row = self.query_one(
            "SELECT * FROM tiktok_profiles WHERE username = ?",
            (username,)
        )
        return self._map_profile_row(row)
    
    def link_scraped_profile(self, scraping_id: int, profile_id: int, is_enriched: bool = False) -> bool:
        """Link a scraped profile to a scraping session via junction table."""
        try:
            self.execute(
                """INSERT OR IGNORE INTO tiktok_scraped_profiles (scraping_id, profile_id, is_enriched)
                   VALUES (?, ?, ?)""",
                (scraping_id, profile_id, 1 if is_enriched else 0)
            )
            return True
        except Exception as e:
            logger.error(f"Error linking scraped profile: {e}")
            return False
    
    def save_scraped_profile(self, scraping_id: int, profile: dict) -> None:
        """Upsert a TikTok profile and link it to a scraping session."""
        username = profile.get('username', '')
        if not username:
            return
        
        profile_id, _ = self.get_or_create_profile(
            username,
            display_name=profile.get('display_name', ''),
            followers_count=profile.get('followers_count', 0),
            following_count=profile.get('following_count', 0),
            likes_count=profile.get('likes_count', 0),
            videos_count=profile.get('posts_count', 0),
            is_private=profile.get('is_private', False),
            is_verified=profile.get('is_verified', False),
            biography=profile.get('bio', '')
        )
        
        if scraping_id:
            self.link_scraped_profile(scraping_id, profile_id, profile.get('is_enriched', False))
    
    # ============================================
    # INTERACTIONS
    # ============================================
    
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
            return cursor.lastrowid
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
            SELECT COUNT(*) as count FROM tiktok_interaction_history
            WHERE account_id = ?
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
            SELECT ih.*, tp.username as target_username
            FROM tiktok_interaction_history ih
            JOIN tiktok_profiles tp ON ih.profile_id = tp.profile_id
            WHERE ih.account_id = ?
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
            FROM tiktok_interaction_history ih
            JOIN tiktok_sessions ts ON ih.session_id = ts.session_id
            WHERE ih.account_id = ?
            AND ts.target = ?
            AND ih.interaction_time >= datetime('now', '-' || ? || ' hours')
            """,
            (account_id, target_username, hours),
        )
        return row['count'] if row else 0
    
    def get_interactions_by_session(self, session_id: int) -> List[Dict[str, Any]]:
        """Get interactions by session"""
        rows = self.query(
            "SELECT * FROM tiktok_interaction_history WHERE session_id = ? ORDER BY interaction_time DESC",
            (session_id,)
        )
        return [{**dict(r), 'success': bool(dict(r).get('success', 0))} for r in rows]
    
    # ============================================
    # FILTERED PROFILES
    # ============================================
    
    def is_profile_filtered(self, username: str, account_id: int) -> bool:
        """Check if a profile is filtered"""
        row = self.query_one(
            "SELECT COUNT(*) as count FROM tiktok_filtered_profiles WHERE username = ? AND account_id = ?",
            (username, account_id)
        )
        return (row['count'] if row else 0) > 0
    
    def record_filtered_profile(
        self,
        account_id: int,
        profile_id: int,
        username: str,
        reason: str,
        source_type: str = 'GENERAL',
        source_name: str = 'unknown',
        session_id: Optional[int] = None
    ) -> bool:
        """Record a filtered profile"""
        try:
            self.execute(
                """INSERT OR REPLACE INTO tiktok_filtered_profiles 
                   (profile_id, account_id, username, reason, source_type, source_name, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (profile_id, account_id, username, reason, source_type, source_name, session_id)
            )
            return True
        except Exception as e:
            logger.error(f"Error recording filtered TikTok profile: {e}")
            return False

    def record_filtered_profile_for_username(
        self,
        account_id: int,
        username: str,
        reason: str,
        source_type: str,
        source_name: str,
        session_id: Optional[int] = None,
    ) -> bool:
        """Record a filtered TikTok profile, creating the profile row if needed."""
        try:
            profile_id, _ = self.get_or_create_profile(username)
            result = self.record_filtered_profile(
                account_id=account_id,
                profile_id=profile_id,
                username=username,
                reason=reason,
                source_type=source_type,
                source_name=source_name,
                session_id=session_id,
            )
            if result:
                logger.debug(f"Recorded TikTok filtered profile: {username} ({reason})")
            return result
        except Exception as e:
            logger.error(f"Error recording TikTok filtered profile: {e}")
            return False
    
    # ============================================
    # MAPPERS
    # ============================================
    
    def _map_profile_row(self, row) -> Optional[Dict[str, Any]]:
        """Map database row to dict"""
        if row is None:
            return None
        row_dict = dict(row)
        return {
            **row_dict,
            'is_private': bool(row_dict.get('is_private', 0)),
            'is_verified': bool(row_dict.get('is_verified', 0))
        }
