"""Database facade for TikTok follow graph sync state.

Same shape as `InstagramFollowGraphService`, and deliberately the same STORE: `social_graph_sync`
is a unified table keyed on `(platform, account_id, username, direction)`. What this facade adds
is the platform binding, because the repository defaults to Instagram and every one of its
queries used to say so in SQL.

Kept as a separate facade rather than a `platform=` argument on the Instagram one: the callers
are platform-local workflows, and a service whose name says Instagram while it writes TikTok rows
is exactly how a run ends up filed under the wrong platform.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from taktik.core.database.local.service import get_local_database

log = logger.bind(module="tiktok-follow-graph")

PLATFORM = "tiktok"


class TikTokFollowGraphService:
    """Facade for TikTok follow-history and follow graph sync bookkeeping."""

    @classmethod
    def _repository(cls):
        return get_local_database().social_graph.for_platform(PLATFORM)

    @classmethod
    def has_bot_follow_record(cls, username: str, account_id: int) -> bool:
        """Whether the bot account successfully followed this handle before."""
        if not account_id:
            return False
        try:
            return cls._repository().has_bot_follow_record(username=username, account_id=account_id)
        except Exception as exc:
            log.debug(f"Error checking bot follow record for @{username}: {exc}")
            return False

    @classmethod
    def get_days_since_follow(cls, username: str, account_id: int) -> Optional[int]:
        """Full days since the most recent successful follow, or None."""
        if not account_id:
            return None
        try:
            return cls._repository().get_days_since_follow(username=username, account_id=account_id)
        except Exception as exc:
            log.debug(f"Error getting days since follow for @{username}: {exc}")
            return None

    @classmethod
    def upsert_following(
        cls,
        username: str,
        display_name: str = "",
        account_id: int = 0,
        followed_by_bot: bool = False,
        is_reciprocal: Optional[bool] = None,
        source: str = "sync",
    ) -> str:
        """Record that the operated account follows `username`. Returns new/updated/error."""
        if not account_id or not username:
            return "error"
        try:
            result = cls._repository().upsert_following(
                username=username,
                display_name=display_name,
                account_id=account_id,
                followed_by_bot=followed_by_bot,
                source=source,
            )
            if is_reciprocal is not None:
                cls._repository().set_following_follower_back(
                    username=username, account_id=account_id, is_follower_back=is_reciprocal
                )
            return result
        except Exception as exc:
            log.debug(f"Error in upsert_following for @{username}: {exc}")
            return "error"

    @classmethod
    def upsert_follower(
        cls,
        username: str,
        account_id: int = 0,
        display_name: str = "",
        is_following_back: Optional[bool] = None,
        source: str = "sync",
    ) -> str:
        """Record that `username` follows the operated account. Returns new/updated/error."""
        if not account_id or not username:
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
            log.debug(f"Error in upsert_follower for @{username}: {exc}")
            return "error"

    @classmethod
    def get_active_following_usernames(cls, account_id: int) -> set[str]:
        """Handles the account still follows, lowercased. Empty on any error."""
        if not account_id:
            return set()
        try:
            return cls._repository().get_active_following_usernames(account_id=account_id)
        except Exception as exc:
            log.debug(f"Error in get_active_following_usernames: {exc}")
            return set()

    @classmethod
    def get_follower_usernames(cls, account_id: int) -> set[str]:
        """Handles known to follow the account, lowercased. Empty on any error."""
        if not account_id:
            return set()
        try:
            return cls._repository().get_follower_usernames(account_id=account_id)
        except Exception as exc:
            log.debug(f"Error in get_follower_usernames: {exc}")
            return set()

    @classmethod
    def mark_unfollowed(cls, username: str, account_id: int) -> None:
        """Stamp a following row as no longer active."""
        if not account_id or not username:
            return
        try:
            cls._repository().mark_unfollowed(username=username, account_id=account_id)
        except Exception as exc:
            log.debug(f"Error marking @{username} as unfollowed: {exc}")


__all__ = ["TikTokFollowGraphService", "PLATFORM"]
