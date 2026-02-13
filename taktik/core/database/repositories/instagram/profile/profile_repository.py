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
                website, profile_pic_path, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                kwargs.get('notes')
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
            'notes': 'notes'
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
