"""
Interaction Repository - Manages interaction_history and filtered_profiles tables
"""

from typing import Dict, List, Optional, Tuple, Any
from .base_repository import BaseRepository


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
            cursor = self.execute(
                """INSERT INTO interaction_history 
                   (session_id, account_id, profile_id, interaction_type, success, content)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, account_id, profile_id, interaction_type.upper(), 1 if success else 0, content)
            )
            return cursor.lastrowid
        except Exception as e:
            print(f"Error recording interaction: {e}")
            return None
    
    def has_recent_interaction(
        self, 
        account_id: int, 
        profile_id: int, 
        days: int = 7
    ) -> bool:
        """Check if there was a recent interaction with a profile"""
        row = self.query_one(
            """SELECT COUNT(*) as count FROM interaction_history
               WHERE account_id = ? AND profile_id = ?
               AND interaction_time >= datetime('now', '-' || ? || ' days')""",
            (account_id, profile_id, days)
        )
        return (row['count'] if row else 0) > 0
    
    def find_by_account(self, account_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get interactions by account"""
        rows = self.query(
            """SELECT ih.*, ip.username as target_username
               FROM interaction_history ih
               JOIN instagram_profiles ip ON ih.profile_id = ip.profile_id
               WHERE ih.account_id = ?
               ORDER BY ih.interaction_time DESC
               LIMIT ?""",
            (account_id, limit)
        )
        return [self._map_interaction_row(row) for row in rows]
    
    def find_by_session(self, session_id: int) -> List[Dict[str, Any]]:
        """Get interactions by session"""
        rows = self.query(
            """SELECT ih.*, ip.username as target_username
               FROM interaction_history ih
               JOIN instagram_profiles ip ON ih.profile_id = ip.profile_id
               WHERE ih.session_id = ?
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
                """SELECT COUNT(*) as count FROM interaction_history 
                   WHERE account_id = ? AND interaction_type = ?
                   AND interaction_time >= datetime('now', '-' || ? || ' days')""",
                (account_id, interaction_type.upper(), days)
            )
        else:
            row = self.query_one(
                "SELECT COUNT(*) as count FROM interaction_history WHERE account_id = ? AND interaction_type = ?",
                (account_id, interaction_type.upper())
            )
        return row['count'] if row else 0
    
    def get_session_stats(self, session_id: int) -> Dict[str, int]:
        """Get interaction stats for a session"""
        rows = self.query(
            """SELECT interaction_type, COUNT(*) as count
               FROM interaction_history
               WHERE session_id = ?
               GROUP BY interaction_type""",
            (session_id,)
        )
        return {row['interaction_type'].lower(): row['count'] for row in rows}
    
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
        """Record a filtered profile"""
        try:
            self.execute(
                """INSERT OR REPLACE INTO filtered_profiles 
                   (profile_id, account_id, username, reason, source_type, source_name, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (profile_id, account_id, username, reason, source_type, source_name, session_id)
            )
            return True
        except Exception as e:
            print(f"Error recording filtered profile: {e}")
            return False
    
    def is_filtered(self, username: str, account_id: int) -> bool:
        """Check if a profile is filtered for an account"""
        row = self.query_one(
            "SELECT COUNT(*) as count FROM filtered_profiles WHERE username = ? AND account_id = ?",
            (username, account_id)
        )
        return (row['count'] if row else 0) > 0
    
    def get_filtered_usernames(self, usernames: List[str], account_id: int) -> List[str]:
        """Check multiple profiles at once (batch)"""
        if not usernames:
            return []
        
        placeholders = ','.join('?' * len(usernames))
        rows = self.query(
            f"SELECT username FROM filtered_profiles WHERE account_id = ? AND username IN ({placeholders})",
            (account_id, *usernames)
        )
        return [row['username'] for row in rows]
    
    def get_filtered_profiles(self, account_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get filtered profiles for an account"""
        rows = self.query(
            "SELECT * FROM filtered_profiles WHERE account_id = ? ORDER BY filtered_at DESC LIMIT ?",
            (account_id, limit)
        )
        return self.rows_to_dicts(rows)
    
    def remove_filtered(self, username: str, account_id: int) -> bool:
        """Remove a profile from filtered list"""
        cursor = self.execute(
            "DELETE FROM filtered_profiles WHERE username = ? AND account_id = ?",
            (username, account_id)
        )
        return cursor.rowcount > 0
    
    def count_filtered(self, account_id: int) -> int:
        """Count filtered profiles for an account"""
        row = self.query_one(
            "SELECT COUNT(*) as count FROM filtered_profiles WHERE account_id = ?",
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
