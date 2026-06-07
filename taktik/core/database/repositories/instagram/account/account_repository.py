"""
Account Repository - Manages instagram_accounts table
"""

from typing import Dict, List, Optional, Tuple, Any
from ..._base.base_repository import BaseRepository


class AccountRepository(BaseRepository):
    """Repository for Instagram accounts"""
    
    def get_or_create(
        self, 
        username: str, 
        is_bot: bool = True, 
        user_id: Optional[int] = None, 
        license_id: Optional[int] = None
    ) -> Tuple[int, bool]:
        """
        Get or create an Instagram account.
        Returns: (account_id, created)
        """
        row = self.query_one(
            "SELECT account_id FROM instagram_accounts WHERE username = ?",
            (username,)
        )
        
        if row:
            return row['account_id'], False
        
        cursor = self.execute(
            """INSERT INTO instagram_accounts (username, is_bot, user_id, license_id)
               VALUES (?, ?, ?, ?)""",
            (username, 1 if is_bot else 0, user_id, license_id)
        )

        account_id = cursor.lastrowid
        self._mirror_to_unified(account_id)
        return account_id, True

    def _mirror_to_unified(self, account_id: int) -> None:
        """Re-mirror the base account fields into the unified `accounts` table (Vague B
        Phase A). Best-effort; only base columns (the bot never writes the Electron
        business columns, so ON CONFLICT does not clobber them)."""
        try:
            self.execute(
                """INSERT INTO accounts
                       (platform, legacy_account_id, username, is_bot, user_id, license_id, created_at)
                   SELECT 'instagram', account_id, username, is_bot, user_id, license_id, created_at
                   FROM instagram_accounts WHERE account_id = ?
                   ON CONFLICT(platform, legacy_account_id) DO UPDATE SET
                       username = excluded.username, is_bot = excluded.is_bot,
                       user_id = excluded.user_id, license_id = excluded.license_id,
                       updated_at = datetime('now')""",
                (account_id,)
            )
        except Exception:
            pass
    
    def find_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Find account by username"""
        row = self.query_one(
            "SELECT * FROM instagram_accounts WHERE username = ?",
            (username,)
        )
        return self._map_row(row)
    
    def find_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Find account by ID"""
        row = self.query_one(
            "SELECT * FROM instagram_accounts WHERE account_id = ?",
            (account_id,)
        )
        return self._map_row(row)
    
    def find_all(self) -> List[Dict[str, Any]]:
        """Get all accounts"""
        rows = self.query(
            "SELECT * FROM instagram_accounts ORDER BY created_at DESC"
        )
        return [self._map_row(row) for row in rows]
    
    def update(self, account_id: int, **kwargs) -> bool:
        """Update account fields"""
        if not kwargs:
            return False
        
        sets = []
        values = []
        
        for key, value in kwargs.items():
            if key == 'is_bot':
                sets.append('is_bot = ?')
                values.append(1 if value else 0)
            elif key in ('username', 'user_id', 'license_id'):
                sets.append(f'{key} = ?')
                values.append(value)
        
        if not sets:
            return False
        
        values.append(account_id)
        cursor = self.execute(
            f"UPDATE instagram_accounts SET {', '.join(sets)} WHERE account_id = ?",
            tuple(values)
        )

        if cursor.rowcount > 0:
            self._mirror_to_unified(account_id)
        return cursor.rowcount > 0
    
    def delete(self, account_id: int) -> bool:
        """Delete account"""
        cursor = self.execute(
            "DELETE FROM instagram_accounts WHERE account_id = ?",
            (account_id,)
        )
        return cursor.rowcount > 0
    
    def _map_row(self, row) -> Optional[Dict[str, Any]]:
        """Map database row to dict"""
        if row is None:
            return None
        row_dict = dict(row)
        return {
            **row_dict,
            'is_bot': bool(row_dict.get('is_bot', 0))
        }
