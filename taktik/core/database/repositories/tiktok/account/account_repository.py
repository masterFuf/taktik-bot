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
        """Get or create a TikTok account (unified `accounts`, platform='tiktok')."""
        row = self.query_one(
            "SELECT legacy_account_id AS account_id FROM accounts WHERE platform = 'tiktok' AND username = ?",
            (username,)
        )

        if row:
            return row['account_id'], False

        # account_id = per-platform legacy_account_id, generated atomically.
        self.execute(
            """INSERT INTO accounts (platform, legacy_account_id, username, display_name, is_bot, user_id, license_id, created_at, updated_at)
               SELECT 'tiktok',
                      COALESCE((SELECT MAX(legacy_account_id) FROM accounts WHERE platform='tiktok'), 0) + 1,
                      ?, ?, ?, ?, ?, datetime('now'), datetime('now')""",
            (username, display_name, 1 if is_bot else 0, user_id, license_id)
        )
        created = self.query_one(
            "SELECT legacy_account_id AS account_id FROM accounts WHERE platform = 'tiktok' AND username = ?",
            (username,)
        )
        return (created['account_id'] if created else None), True

    def find_account_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Find account by username"""
        row = self.query_one(
            "SELECT *, legacy_account_id AS account_id FROM accounts WHERE platform = 'tiktok' AND username = ?",
            (username,)
        )
        if not row:
            return None
        row_dict = dict(row)
        return {**row_dict, 'is_bot': bool(row_dict.get('is_bot', 0))}

    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """Get all TikTok accounts"""
        rows = self.query("SELECT *, legacy_account_id AS account_id FROM accounts WHERE platform = 'tiktok' ORDER BY created_at DESC")
        return [{**dict(r), 'is_bot': bool(dict(r).get('is_bot', 0))} for r in rows]
