"""TikTok account repository methods."""

from typing import Any, Dict, List, Optional, Tuple


class TikTokAccountRepositoryMixin:
    """SQL owner for `tiktok_accounts`."""

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
