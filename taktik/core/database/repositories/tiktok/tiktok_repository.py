"""
TikTok Repository - Manages tiktok_accounts, tiktok_profiles, tiktok_sessions, 
tiktok_interaction_history, tiktok_filtered_profiles, tiktok_daily_stats
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from loguru import logger

from .._base.base_repository import BaseRepository


class TikTokRepository(BaseRepository):
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
            print(f"Error linking scraped profile: {e}")
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
    # SESSIONS
    # ============================================
    
    def create_session(
        self,
        account_id: int,
        session_name: str,
        workflow_type: str,
        target: Optional[str] = None,
        config_used: Optional[dict] = None
    ) -> Optional[int]:
        """Create a new TikTok session"""
        try:
            cursor = self.execute(
                """INSERT INTO tiktok_sessions (account_id, session_name, workflow_type, target, config_used)
                   VALUES (?, ?, ?, ?, ?)""",
                (account_id, session_name[:100], workflow_type, target[:50] if target else None,
                 json.dumps(self._redact_sensitive(config_used)) if config_used else None)
            )
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error creating TikTok session: {e}")
            return None
    
    def update_session(self, session_id: int, **kwargs) -> bool:
        """Update session stats"""
        updates = ["updated_at = datetime('now')"]
        values = []
        
        field_mapping = {
            'status': 'status',
            'end_time': 'end_time',
            'duration_seconds': 'duration_seconds',
            'profiles_visited': 'profiles_visited',
            'posts_watched': 'posts_watched',
            'likes': 'likes',
            'follows': 'follows',
            'favorites': 'favorites',
            'comments': 'comments',
            'shares': 'shares',
            'errors': 'errors',
            'error_message': 'error_message'
        }
        
        for key, column in field_mapping.items():
            if key in kwargs and kwargs[key] is not None:
                updates.append(f'{column} = ?')
                values.append(kwargs[key])
        
        if len(updates) == 1:  # Only updated_at
            return True
        
        values.append(session_id)
        cursor = self.execute(
            f"UPDATE tiktok_sessions SET {', '.join(updates)} WHERE session_id = ?",
            tuple(values)
        )
        return cursor.rowcount > 0

    def end_session(
        self,
        session_id: int,
        status: str = 'COMPLETED',
        error_message: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """End a TikTok session with final stats."""
        try:
            row = self.query_one(
                "SELECT start_time FROM tiktok_sessions WHERE session_id = ?",
                (session_id,),
            )

            duration = 0
            if row and row['start_time']:
                start = datetime.fromisoformat(row['start_time'].replace('Z', '+00:00'))
                duration = int((datetime.now() - start.replace(tzinfo=None)).total_seconds())

            update_data = {
                'status': status,
                'end_time': datetime.now().isoformat(),
                'duration_seconds': duration,
                'error_message': error_message,
            }

            if stats:
                update_data.update({
                    'profiles_visited': stats.get('profiles_visited', 0),
                    'posts_watched': stats.get('posts_watched', 0),
                    'likes': stats.get('likes', 0),
                    'follows': stats.get('follows', 0),
                    'favorites': stats.get('favorites', 0),
                    'comments': stats.get('comments', 0),
                    'shares': stats.get('shares', 0),
                    'errors': stats.get('errors', 0),
                })

            return self.update_session(session_id, **update_data)
        except Exception as e:
            logger.error(f"Error ending TikTok session: {e}")
            return False

    def get_sessions(
        self,
        account_id: Optional[int] = None,
        limit: int = 50,
        workflow_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get TikTok sessions with optional filters."""
        query = "SELECT * FROM tiktok_sessions WHERE 1=1"
        params = []

        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)

        if workflow_type:
            query += " AND workflow_type = ?"
            params.append(workflow_type)

        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)

        return [dict(row) for row in self.query(query, tuple(params))]
    
    def get_sessions_by_account(self, account_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get sessions by account"""
        rows = self.query(
            "SELECT * FROM tiktok_sessions WHERE account_id = ? ORDER BY start_time DESC LIMIT ?",
            (account_id, limit)
        )
        return [dict(row) for row in rows]
    
    def get_all_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all sessions"""
        rows = self.query(
            "SELECT * FROM tiktok_sessions ORDER BY start_time DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in rows]
    
    def get_session_stats(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get session stats"""
        row = self.query_one(
            "SELECT * FROM tiktok_sessions WHERE session_id = ?",
            (session_id,)
        )
        return dict(row) if row else None
    
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
    # DAILY STATS
    # ============================================
    
    def get_or_create_daily_stats(self, account_id: int, date: Optional[str] = None) -> Dict[str, Any]:
        """Get or create daily stats"""
        from datetime import datetime
        target_date = date or datetime.now().strftime('%Y-%m-%d')
        
        row = self.query_one(
            "SELECT * FROM tiktok_daily_stats WHERE account_id = ? AND date = ?",
            (account_id, target_date)
        )
        
        if not row:
            self.execute(
                "INSERT INTO tiktok_daily_stats (account_id, date) VALUES (?, ?)",
                (account_id, target_date)
            )
            row = self.query_one(
                "SELECT * FROM tiktok_daily_stats WHERE account_id = ? AND date = ?",
                (account_id, target_date)
            )
        
        return dict(row) if row else {}
    
    def increment_stat(self, account_id: int, stat_name: str, amount: int = 1) -> bool:
        """Increment a stat"""
        from datetime import datetime
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
            f"""UPDATE tiktok_daily_stats 
                SET {stat_name} = {stat_name} + ?, updated_at = datetime('now')
                WHERE account_id = ? AND date = ?""",
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
        """Get TikTok daily stats for an account."""
        rows = self.query(
            """
            SELECT * FROM tiktok_daily_stats
            WHERE account_id = ? AND date >= date('now', '-' || ? || ' days')
            ORDER BY date DESC
            """,
            (account_id, days),
        )
        return [dict(row) for row in rows]
    
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
