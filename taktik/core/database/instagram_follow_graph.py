"""Database facade for Instagram follow graph sync state.

This service keeps legacy unfollow/sync workflows out of platform-local SQL while
repositories for `following_sync` / `followers_sync` are still being introduced.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from loguru import logger

from taktik.core.database.local.service import get_local_database

log = logger.bind(module="instagram-follow-graph")


class InstagramFollowGraphService:
    """Facade for follow-history and follow graph sync bookkeeping."""

    @staticmethod
    def _local_db():
        return get_local_database()

    @classmethod
    def has_bot_follow_record(cls, username: str, account_id: int) -> bool:
        """Return whether the bot account successfully followed this username before."""
        if not account_id:
            return False

        try:
            conn = cls._local_db()._get_connection()
            cursor = conn.execute(
                "SELECT profile_id FROM instagram_profiles WHERE username = ? COLLATE NOCASE",
                (username,),
            )
            row = cursor.fetchone()
            if not row:
                return False

            profile_id = row["profile_id"] if isinstance(row, dict) else row[0]
            cursor = conn.execute(
                """SELECT 1 FROM interaction_history
                   WHERE account_id = ? AND profile_id = ? AND interaction_type = 'FOLLOW' AND success = 1
                   LIMIT 1""",
                (account_id, profile_id),
            )
            return cursor.fetchone() is not None
        except Exception as exc:
            log.debug(f"Error checking bot follow record for @{username}: {exc}")
            return False

    @classmethod
    def get_days_since_follow(cls, username: str, account_id: int) -> Optional[int]:
        """Return the number of full days since the most recent successful follow."""
        if not account_id:
            return None

        try:
            conn = cls._local_db()._get_connection()
            cursor = conn.execute(
                "SELECT profile_id FROM instagram_profiles WHERE username = ? COLLATE NOCASE",
                (username,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            profile_id = row["profile_id"] if isinstance(row, dict) else row[0]
            cursor = conn.execute(
                """SELECT interaction_time FROM interaction_history
                   WHERE account_id = ? AND profile_id = ? AND interaction_type = 'FOLLOW' AND success = 1
                   ORDER BY interaction_time DESC LIMIT 1""",
                (account_id, profile_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            follow_time_str = row["interaction_time"] if isinstance(row, dict) else row[0]
            if not follow_time_str:
                return None

            return (datetime.now() - datetime.fromisoformat(follow_time_str)).days
        except Exception as exc:
            log.debug(f"Error getting days since follow for @{username}: {exc}")
            return None

    @classmethod
    def sync_following_upsert(
        cls,
        username: str,
        display_name: str,
        account_id: int,
        followed_by_bot: bool = False,
        source: str = "sync",
    ) -> str:
        """Insert or update a following entry in `following_sync`."""
        if not account_id:
            return "error"

        try:
            conn = cls._local_db()._get_connection()
            cursor = conn.execute(
                "SELECT id FROM following_sync WHERE account_id = ? AND username = ? COLLATE NOCASE",
                (account_id, username),
            )
            existing = cursor.fetchone()

            if existing:
                conn.execute(
                    """UPDATE following_sync
                       SET display_name = ?, last_seen_at = datetime('now'),
                           followed_by_bot = ?, source = ?
                       WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                    (display_name, int(followed_by_bot), source, account_id, username),
                )
                conn.commit()
                return "updated"

            conn.execute(
                """INSERT INTO following_sync
                   (account_id, username, display_name, followed_by_bot, source)
                   VALUES (?, ?, ?, ?, ?)""",
                (account_id, username, display_name, int(followed_by_bot), source),
            )
            conn.commit()
            return "new"
        except Exception as exc:
            log.debug(f"Error in sync_following_upsert for @{username}: {exc}")
            return "error"

    @classmethod
    def get_following_sync_usernames(cls, account_id: int) -> set[str]:
        """Return known active followings for an account as lowercase usernames."""
        if not account_id:
            return set()

        try:
            conn = cls._local_db()._get_connection()
            cursor = conn.execute(
                "SELECT username FROM following_sync WHERE account_id = ? AND unfollowed_at IS NULL",
                (account_id,),
            )
            return {row[0].lower() for row in cursor.fetchall()}
        except Exception as exc:
            log.debug(f"Error in get_following_sync_usernames: {exc}")
            return set()

    @classmethod
    def mark_not_follower_back(cls, username: str, account_id: int) -> None:
        """Mark a following as not following back."""
        cls._set_following_follower_back_flag(username=username, account_id=account_id, is_follower_back=False)

    @classmethod
    def mark_follower_back(cls, username: str, account_id: int) -> None:
        """Mark a following as following back."""
        cls._set_following_follower_back_flag(username=username, account_id=account_id, is_follower_back=True)

    @classmethod
    def _set_following_follower_back_flag(
        cls,
        username: str,
        account_id: int,
        is_follower_back: bool,
    ) -> None:
        if not account_id:
            return

        try:
            conn = cls._local_db()._get_connection()
            conn.execute(
                """UPDATE following_sync SET is_follower_back = ?, last_seen_at = datetime('now')
                   WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                (int(is_follower_back), account_id, username),
            )
            conn.commit()
        except Exception as exc:
            flag_name = "mark_follower_back" if is_follower_back else "mark_not_follower_back"
            log.debug(f"Error in {flag_name} for @{username}: {exc}")

    @classmethod
    def mark_unfollowed(cls, username: str, account_id: int) -> None:
        """Stamp an active following entry as unfollowed."""
        if not account_id:
            return

        try:
            conn = cls._local_db()._get_connection()
            conn.execute(
                """UPDATE following_sync SET unfollowed_at = datetime('now')
                   WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                (account_id, username),
            )
            conn.commit()
        except Exception as exc:
            log.debug(f"Error in mark_unfollowed for @{username}: {exc}")

    @classmethod
    def sync_follower_upsert(
        cls,
        username: str,
        account_id: int,
        display_name: str = "",
        is_following_back: Optional[bool] = None,
        source: str = "sync",
    ) -> str:
        """Insert or update a follower entry in `followers_sync`."""
        if not account_id:
            return "error"

        try:
            conn = cls._local_db()._get_connection()
            cursor = conn.execute(
                "SELECT id FROM followers_sync WHERE account_id = ? AND username = ? COLLATE NOCASE",
                (account_id, username),
            )
            existing = cursor.fetchone()
            following_back_val = None if is_following_back is None else int(is_following_back)

            if existing:
                conn.execute(
                    """UPDATE followers_sync
                       SET display_name = COALESCE(NULLIF(?, ''), display_name),
                           last_seen_at = datetime('now'),
                           is_following_back = COALESCE(?, is_following_back),
                           source = ?
                       WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                    (display_name, following_back_val, source, account_id, username),
                )
                conn.commit()
                return "updated"

            conn.execute(
                """INSERT INTO followers_sync
                   (account_id, username, display_name, is_following_back, source)
                   VALUES (?, ?, ?, ?, ?)""",
                (account_id, username, display_name, following_back_val, source),
            )
            conn.commit()
            return "new"
        except Exception as exc:
            log.debug(f"Error in sync_follower_upsert for @{username}: {exc}")
            return "error"

    @classmethod
    def get_followers_sync_usernames(cls, account_id: int) -> set[str]:
        """Return known followers for an account as lowercase usernames."""
        if not account_id:
            return set()

        try:
            conn = cls._local_db()._get_connection()
            cursor = conn.execute(
                "SELECT username FROM followers_sync WHERE account_id = ?",
                (account_id,),
            )
            return {row[0].lower() for row in cursor.fetchall()}
        except Exception as exc:
            log.debug(f"Error in get_followers_sync_usernames: {exc}")
            return set()
