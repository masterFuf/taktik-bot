"""Repository for Instagram follow graph sync tables and follow-history lookups."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from loguru import logger

from ..._base.base_repository import BaseRepository


class SocialGraphRepository(BaseRepository):
    """Read/write access for `following_sync`, `followers_sync` and follow lookups."""

    def has_bot_follow_record(self, username: str, account_id: int) -> bool:
        if not account_id:
            return False

        try:
            row = self.query_one(
                "SELECT profile_id FROM instagram_profiles WHERE username = ? COLLATE NOCASE",
                (username,),
            )
            if not row:
                return False

            interaction = self.query_one(
                """SELECT 1 FROM interaction_history
                   WHERE account_id = ? AND profile_id = ? AND interaction_type = 'FOLLOW' AND success = 1
                   LIMIT 1""",
                (account_id, row["profile_id"]),
            )
            return interaction is not None
        except Exception as exc:
            logger.debug(f"Error checking bot follow record for @{username}: {exc}")
            return False

    def get_days_since_follow(self, username: str, account_id: int) -> Optional[int]:
        if not account_id:
            return None

        try:
            row = self.query_one(
                "SELECT profile_id FROM instagram_profiles WHERE username = ? COLLATE NOCASE",
                (username,),
            )
            if not row:
                return None

            follow = self.query_one(
                """SELECT interaction_time FROM interaction_history
                   WHERE account_id = ? AND profile_id = ? AND interaction_type = 'FOLLOW' AND success = 1
                   ORDER BY interaction_time DESC LIMIT 1""",
                (account_id, row["profile_id"]),
            )
            if not follow or not follow["interaction_time"]:
                return None

            return (datetime.now() - datetime.fromisoformat(follow["interaction_time"])).days
        except Exception as exc:
            logger.debug(f"Error getting days since follow for @{username}: {exc}")
            return None

    def upsert_following(
        self,
        username: str,
        display_name: str,
        account_id: int,
        followed_by_bot: bool = False,
        source: str = "sync",
    ) -> str:
        if not account_id:
            return "error"

        try:
            existing = self.query_one(
                "SELECT id FROM following_sync WHERE account_id = ? AND username = ? COLLATE NOCASE",
                (account_id, username),
            )
            if existing:
                self.execute(
                    """UPDATE following_sync
                       SET display_name = ?, last_seen_at = datetime('now'),
                           followed_by_bot = ?, source = ?
                       WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                    (display_name, int(followed_by_bot), source, account_id, username),
                )
                return "updated"

            self.execute(
                """INSERT INTO following_sync
                   (account_id, username, display_name, followed_by_bot, source)
                   VALUES (?, ?, ?, ?, ?)""",
                (account_id, username, display_name, int(followed_by_bot), source),
            )
            return "new"
        except Exception as exc:
            logger.debug(f"Error in upsert_following for @{username}: {exc}")
            return "error"

    def get_active_following_usernames(self, account_id: int) -> set[str]:
        if not account_id:
            return set()

        try:
            rows = self.query(
                "SELECT username FROM following_sync WHERE account_id = ? AND unfollowed_at IS NULL",
                (account_id,),
            )
            return {row["username"].lower() for row in rows}
        except Exception as exc:
            logger.debug(f"Error in get_active_following_usernames: {exc}")
            return set()

    def set_following_follower_back(
        self,
        username: str,
        account_id: int,
        is_follower_back: bool,
    ) -> None:
        if not account_id:
            return

        try:
            self.execute(
                """UPDATE following_sync SET is_follower_back = ?, last_seen_at = datetime('now')
                   WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                (int(is_follower_back), account_id, username),
            )
        except Exception as exc:
            logger.debug(f"Error updating follower-back flag for @{username}: {exc}")

    def mark_unfollowed(self, username: str, account_id: int) -> None:
        if not account_id:
            return

        try:
            self.execute(
                """UPDATE following_sync SET unfollowed_at = datetime('now')
                   WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                (account_id, username),
            )
        except Exception as exc:
            logger.debug(f"Error marking @{username} as unfollowed: {exc}")

    def upsert_follower(
        self,
        username: str,
        account_id: int,
        display_name: str = "",
        is_following_back: Optional[bool] = None,
        source: str = "sync",
    ) -> str:
        if not account_id:
            return "error"

        try:
            existing = self.query_one(
                "SELECT id FROM followers_sync WHERE account_id = ? AND username = ? COLLATE NOCASE",
                (account_id, username),
            )
            following_back_value = None if is_following_back is None else int(is_following_back)

            if existing:
                self.execute(
                    """UPDATE followers_sync
                       SET display_name = COALESCE(NULLIF(?, ''), display_name),
                           last_seen_at = datetime('now'),
                           is_following_back = COALESCE(?, is_following_back),
                           source = ?
                       WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                    (display_name, following_back_value, source, account_id, username),
                )
                return "updated"

            self.execute(
                """INSERT INTO followers_sync
                   (account_id, username, display_name, is_following_back, source)
                   VALUES (?, ?, ?, ?, ?)""",
                (account_id, username, display_name, following_back_value, source),
            )
            return "new"
        except Exception as exc:
            logger.debug(f"Error in upsert_follower for @{username}: {exc}")
            return "error"

    def get_follower_usernames(self, account_id: int) -> set[str]:
        if not account_id:
            return set()

        try:
            rows = self.query(
                "SELECT username FROM followers_sync WHERE account_id = ?",
                (account_id,),
            )
            return {row["username"].lower() for row in rows}
        except Exception as exc:
            logger.debug(f"Error in get_follower_usernames: {exc}")
            return set()
