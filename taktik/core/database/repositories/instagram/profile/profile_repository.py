"""
Profile Repository - Manages instagram_profiles table
"""

from typing import Dict, List, Optional, Tuple, Any
from ..._base.base_repository import BaseRepository


class ProfileRepository(BaseRepository):
    """Repository for Instagram profiles"""
    
    def get_or_create(self, username: str, **kwargs) -> Tuple[int, bool]:
        """
        Get or create a profile (upsert).
        Returns: (profile_id, created)
        """
        row = self.query_one(
            "SELECT profile_id FROM instagram_profiles WHERE username = ?",
            (username,)
        )
        
        if row:
            # Update existing profile
            profile_id = row['profile_id']
            self._update_profile(profile_id, **kwargs)
            return profile_id, False
        
        # Create new profile
        cursor = self.execute(
            """INSERT INTO instagram_profiles (
                username, full_name, biography, followers_count, following_count,
                posts_count, is_private, is_verified, is_business, business_category,
                website, profile_pic_path, notes, account_based_in, date_joined
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                username,
                kwargs.get('full_name', ''),
                kwargs.get('biography'),
                kwargs.get('followers_count', 0),
                kwargs.get('following_count', 0),
                kwargs.get('posts_count', 0),
                1 if kwargs.get('is_private') else 0,
                1 if kwargs.get('is_verified') else 0,
                1 if kwargs.get('is_business') else 0,
                kwargs.get('business_category'),
                kwargs.get('website'),
                kwargs.get('profile_pic_path'),
                kwargs.get('notes'),
                kwargs.get('account_based_in'),
                kwargs.get('date_joined')
            )
        )
        
        return cursor.lastrowid, True
    
    def _update_profile(self, profile_id: int, **kwargs) -> None:
        """Update profile with non-None values"""
        updates = []
        values = []
        
        field_mapping = {
            'full_name': 'full_name',
            'biography': 'biography',
            'followers_count': 'followers_count',
            'following_count': 'following_count',
            'posts_count': 'posts_count',
            'business_category': 'business_category',
            'website': 'website',
            'profile_pic_path': 'profile_pic_path',
            'notes': 'notes',
            'account_based_in': 'account_based_in',
            'date_joined': 'date_joined',
        }
        
        for key, column in field_mapping.items():
            if key in kwargs and kwargs[key] is not None:
                updates.append(f"{column} = COALESCE(?, {column})")
                values.append(kwargs[key])
        
        # Boolean fields
        for key in ('is_private', 'is_verified', 'is_business'):
            if key in kwargs and kwargs[key] is not None:
                updates.append(f"{key} = COALESCE(?, {key})")
                values.append(1 if kwargs[key] else 0)
        
        if updates:
            updates.append("updated_at = datetime('now')")
            values.append(profile_id)
            self.execute(
                f"UPDATE instagram_profiles SET {', '.join(updates)} WHERE profile_id = ?",
                tuple(values)
            )
    
    def find_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Find profile by username"""
        row = self.query_one(
            "SELECT * FROM instagram_profiles WHERE username = ?",
            (username,)
        )
        return self._map_row(row)

    def find_profiles_with_latest_qualification(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """Batch lookup profiles with latest positive scraping qualification data."""
        if not usernames:
            return []

        placeholders = ','.join('?' * len(usernames))
        rows = self.query(
            f"""
            SELECT
                p.username,
                p.full_name,
                p.biography,
                p.is_business,
                p.ai_niche          AS niche_category,
                p.ai_specific_niche AS niche,
                p.ai_profession     AS profession,
                p.ai_profession_tags AS profession_tags,
                p.location_city     AS cities,
                sp.ai_analysis,
                sp.ai_qualified
            FROM instagram_profiles p
            LEFT JOIN (
                SELECT profile_id,
                       MAX(scraped_at) AS latest,
                       ai_analysis,
                       ai_qualified
                FROM scraped_profiles
                WHERE ai_qualified = 1
                GROUP BY profile_id
            ) sp ON sp.profile_id = p.profile_id
            WHERE p.username IN ({placeholders})
            """,
            tuple(usernames),
        )
        return [dict(row) for row in rows]

    def record_stats_history(self, profile_id: int, profile_data: Dict[str, Any]) -> bool:
        """Record a profile_stats_history snapshot for enriched profile data."""
        cursor = self.execute(
            """
            INSERT INTO profile_stats_history
            (profile_id, followers_count, following_count, posts_count,
             is_verified, external_url, profile_pic_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                profile_data.get('followers_count', 0),
                profile_data.get('following_count', 0),
                profile_data.get('posts_count', 0),
                1 if profile_data.get('is_verified') else 0,
                profile_data.get('external_url'),
                profile_data.get('profile_pic_url'),
            ),
        )
        return cursor.rowcount > 0

    def is_recently_scraped(self, username: str, days: int = 7) -> bool:
        """Check whether a profile was updated within the configured time window."""
        row = self.query_one(
            """
            SELECT profile_id
            FROM instagram_profiles
            WHERE username = ?
            AND updated_at >= datetime('now', '-' || ? || ' days')
            """,
            (username, days),
        )
        return row is not None

    def exists_by_username(self, username: str, days: Optional[int] = None) -> bool:
        """Check if a profile exists, optionally constrained by creation date."""
        if days is None:
            row = self.query_one(
                "SELECT 1 FROM instagram_profiles WHERE username = ? LIMIT 1",
                (username,),
            )
        else:
            row = self.query_one(
                """
                SELECT 1 FROM instagram_profiles
                WHERE username = ?
                AND created_at >= datetime('now', '-' || ? || ' days')
                LIMIT 1
                """,
                (username, days),
            )
        return row is not None

    def get_known_usernames(self, days: Optional[int] = None, limit: int = 10000) -> set:
        """Return usernames already known by the profile table."""
        if days is None:
            rows = self.query(
                """
                SELECT username
                FROM instagram_profiles
                LIMIT ?
                """,
                (limit,),
            )
        else:
            rows = self.query(
                """
                SELECT username
                FROM instagram_profiles
                WHERE created_at >= datetime('now', '-' || ? || ' days')
                LIMIT ?
                """,
                (days, limit),
            )
        return {row['username'] for row in rows}
    
    def find_by_id(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Find profile by ID"""
        row = self.query_one(
            "SELECT * FROM instagram_profiles WHERE profile_id = ?",
            (profile_id,)
        )
        return self._map_row(row)
    
    def find_by_ids(self, profile_ids: List[int]) -> List[Dict[str, Any]]:
        """Find profiles by IDs"""
        if not profile_ids:
            return []
        
        placeholders = ','.join('?' * len(profile_ids))
        rows = self.query(
            f"SELECT * FROM instagram_profiles WHERE profile_id IN ({placeholders})",
            tuple(profile_ids)
        )
        return [self._map_row(row) for row in rows]
    
    def search_by_username(self, pattern: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search profiles by username pattern"""
        rows = self.query(
            "SELECT * FROM instagram_profiles WHERE username LIKE ? ORDER BY followers_count DESC LIMIT ?",
            (f"%{pattern}%", limit)
        )
        return [self._map_row(row) for row in rows]
    
    def find_business_profiles(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get business profiles"""
        rows = self.query(
            "SELECT * FROM instagram_profiles WHERE is_business = 1 ORDER BY followers_count DESC LIMIT ?",
            (limit,)
        )
        return [self._map_row(row) for row in rows]
    
    def count(self) -> int:
        """Count total profiles"""
        row = self.query_one("SELECT COUNT(*) as count FROM instagram_profiles")
        return row['count'] if row else 0
    
    def delete(self, profile_id: int) -> bool:
        """Delete profile"""
        cursor = self.execute(
            "DELETE FROM instagram_profiles WHERE profile_id = ?",
            (profile_id,)
        )
        return cursor.rowcount > 0
    
    def _map_row(self, row) -> Optional[Dict[str, Any]]:
        """Map database row to dict"""
        if row is None:
            return None
        # Convert sqlite3.Row to dict first to use .get() safely
        row_dict = dict(row)
        return {
            **row_dict,
            'is_private': bool(row_dict.get('is_private', 0)),
            'is_verified': bool(row_dict.get('is_verified', 0)),
            'is_business': bool(row_dict.get('is_business', 0))
        }
