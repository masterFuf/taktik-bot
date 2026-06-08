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
            "SELECT legacy_account_id AS account_id FROM accounts WHERE platform = 'instagram' AND username = ?",
            (username,)
        )

        if row:
            return row['account_id'], False

        # Vague B: write the unified `accounts` table; account_id = per-platform
        # legacy_account_id, generated atomically (single INSERT...SELECT MAX+1).
        self.execute(
            """INSERT INTO accounts (platform, legacy_account_id, username, is_bot, user_id, license_id, created_at, updated_at)
               SELECT 'instagram',
                      COALESCE((SELECT MAX(legacy_account_id) FROM accounts WHERE platform='instagram'), 0) + 1,
                      ?, ?, ?, ?, datetime('now'), datetime('now')""",
            (username, 1 if is_bot else 0, user_id, license_id)
        )
        created = self.query_one(
            "SELECT legacy_account_id AS account_id FROM accounts WHERE platform = 'instagram' AND username = ?",
            (username,)
        )
        return (created['account_id'] if created else None), True

    def find_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Find account by username (ORM-first, fallback to raw sqlite3)."""
        row = self.query_one_orm_first(
            "SELECT *, legacy_account_id AS account_id FROM accounts WHERE platform = 'instagram' AND username = ?",
            (username,)
        )
        return self._map_row(row)

    def find_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Find account by ID (ORM-first, fallback to raw sqlite3)."""
        row = self.query_one_orm_first(
            "SELECT *, legacy_account_id AS account_id FROM accounts WHERE platform = 'instagram' AND legacy_account_id = ?",
            (account_id,)
        )
        return self._map_row(row)

    def find_all(self) -> List[Dict[str, Any]]:
        """Get all accounts (ORM-first, fallback to raw sqlite3)."""
        rows = self.query_orm_first(
            "SELECT *, legacy_account_id AS account_id FROM accounts WHERE platform = 'instagram' ORDER BY created_at DESC"
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
            f"UPDATE accounts SET {', '.join(sets)} WHERE platform = 'instagram' AND legacy_account_id = ?",
            tuple(values)
        )
        return cursor.rowcount > 0

    def delete(self, account_id: int) -> bool:
        """Delete account"""
        cursor = self.execute(
            "DELETE FROM accounts WHERE platform = 'instagram' AND legacy_account_id = ?",
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
