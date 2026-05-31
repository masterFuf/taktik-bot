"""
TikTok Repository - Manages tiktok_accounts, tiktok_profiles, tiktok_sessions, 
tiktok_interaction_history, tiktok_filtered_profiles, tiktok_daily_stats
"""

from typing import Dict, List, Optional, Any, Tuple

from loguru import logger

from .._base.base_repository import BaseRepository
from .filtering import TikTokFilteredProfileRepositoryMixin
from .interaction import TikTokInteractionRepositoryMixin
from .session import TikTokSessionRepositoryMixin
from .stats import TikTokStatsRepositoryMixin


class TikTokRepository(
    TikTokFilteredProfileRepositoryMixin,
    TikTokInteractionRepositoryMixin,
    TikTokStatsRepositoryMixin,
    TikTokSessionRepositoryMixin,
    BaseRepository,
):
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
