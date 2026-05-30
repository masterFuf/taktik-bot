"""Database facade for Instagram follow graph sync state.

This service keeps legacy unfollow/sync workflows out of platform-local SQL while
repositories for `following_sync` / `followers_sync` are still being introduced.
"""

from __future__ import annotations

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
    def _repository(cls):
        return cls._local_db().social_graph

    @classmethod
    def has_bot_follow_record(cls, username: str, account_id: int) -> bool:
        """Return whether the bot account successfully followed this username before."""
        if not account_id:
            return False

        try:
            return cls._repository().has_bot_follow_record(username=username, account_id=account_id)
        except Exception as exc:
            log.debug(f"Error checking bot follow record for @{username}: {exc}")
            return False

    @classmethod
    def get_days_since_follow(cls, username: str, account_id: int) -> Optional[int]:
        """Return the number of full days since the most recent successful follow."""
        if not account_id:
            return None

        try:
            return cls._repository().get_days_since_follow(username=username, account_id=account_id)
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
            return cls._repository().upsert_following(
                username=username,
                display_name=display_name,
                account_id=account_id,
                followed_by_bot=followed_by_bot,
                source=source,
            )
        except Exception as exc:
            log.debug(f"Error in sync_following_upsert for @{username}: {exc}")
            return "error"

    @classmethod
    def get_following_sync_usernames(cls, account_id: int) -> set[str]:
        """Return known active followings for an account as lowercase usernames."""
        if not account_id:
            return set()

        try:
            return cls._repository().get_active_following_usernames(account_id=account_id)
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
            cls._repository().set_following_follower_back(
                username=username,
                account_id=account_id,
                is_follower_back=is_follower_back,
            )
        except Exception as exc:
            flag_name = "mark_follower_back" if is_follower_back else "mark_not_follower_back"
            log.debug(f"Error in {flag_name} for @{username}: {exc}")

    @classmethod
    def mark_unfollowed(cls, username: str, account_id: int) -> None:
        """Stamp an active following entry as unfollowed."""
        if not account_id:
            return

        try:
            cls._repository().mark_unfollowed(username=username, account_id=account_id)
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
            return cls._repository().upsert_follower(
                username=username,
                account_id=account_id,
                display_name=display_name,
                is_following_back=is_following_back,
                source=source,
            )
        except Exception as exc:
            log.debug(f"Error in sync_follower_upsert for @{username}: {exc}")
            return "error"

    @classmethod
    def get_followers_sync_usernames(cls, account_id: int) -> set[str]:
        """Return known followers for an account as lowercase usernames."""
        if not account_id:
            return set()

        try:
            return cls._repository().get_follower_usernames(account_id=account_id)
        except Exception as exc:
            log.debug(f"Error in get_followers_sync_usernames: {exc}")
            return set()
