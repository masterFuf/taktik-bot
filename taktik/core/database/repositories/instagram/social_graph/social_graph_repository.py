"""Repository for the follow graph sync table and follow-history lookups.

`social_graph_sync` is a unified table: it has a `platform` column and its unique key is
`(platform, account_id, username, direction)`. Every query here hardcoded 'instagram'
anyway, so the table was multi-platform and its only reader was not -- a TikTok sync had
nowhere to write and nothing to read back.

The platform is an attribute now, defaulted to 'instagram' so every existing caller is
unchanged, and the profile lookups go through `social_profiles` filtered on it instead of
through the `instagram_profiles` view -- which is Instagram-only BY CONSTRUCTION and would
have answered a TikTok handle with an Instagram namesake's follow history.
"""

from __future__ import annotations

from copy import copy
from datetime import datetime
from typing import Optional

from loguru import logger

from ..._base.base_repository import BaseRepository


class SocialGraphRepository(BaseRepository):
    """Read/write access for the unified `social_graph_sync` follow graph + follow lookups."""

    #: Which platform's half of the unified tables this instance reads and writes.
    platform: str = "instagram"

    def for_platform(self, platform: str) -> "SocialGraphRepository":
        """Return a view of this repository bound to another platform.

        Shares the connection and the ORM engine: a lens on the same tables, not a second
        repository with its own state.
        """
        if platform == self.platform:
            return self
        bound = copy(self)
        bound.platform = platform
        return bound

    def _profile_id(self, username: str) -> Optional[int]:
        """Resolve a handle to the id `interactions.profile_id` actually points at.

        That is `social_profiles.legacy_profile_id`, which the `instagram_profiles` view
        exposes under the alias `profile_id`. Reading the view here would silently scope
        every platform to Instagram.
        """
        row = self.query_one_orm_first(
            "SELECT legacy_profile_id AS profile_id FROM social_profiles "
            "WHERE platform = ? AND username = ? COLLATE NOCASE",
            (self.platform, username),
        )
        return row["profile_id"] if row else None

    def has_bot_follow_record(self, username: str, account_id: int) -> bool:
        if not account_id:
            return False

        try:
            profile_id = self._profile_id(username)
            if profile_id is None:
                return False

            interaction = self.query_one_orm_first(
                """SELECT 1 FROM interactions
                   WHERE platform = ? AND account_id = ? AND profile_id = ? AND interaction_type = 'FOLLOW' AND success = 1
                   LIMIT 1""",
                (self.platform, account_id, profile_id),
            )
            return interaction is not None
        except Exception as exc:
            logger.debug(f"Error checking bot follow record for @{username}: {exc}")
            return False

    def get_days_since_follow(self, username: str, account_id: int) -> Optional[int]:
        if not account_id:
            return None

        try:
            profile_id = self._profile_id(username)
            if profile_id is None:
                return None

            follow = self.query_one_orm_first(
                """SELECT interaction_time FROM interactions
                   WHERE platform = ? AND account_id = ? AND profile_id = ? AND interaction_type = 'FOLLOW' AND success = 1
                   ORDER BY interaction_time DESC LIMIT 1""",
                (self.platform, account_id, profile_id),
            )
            if not follow or not follow["interaction_time"]:
                return None

            return (datetime.now() - datetime.fromisoformat(follow["interaction_time"])).days
        except Exception as exc:
            logger.debug(f"Error getting days since follow for @{username}: {exc}")
            return None

    def _upsert_social_graph(
        self,
        account_id: int,
        username: str,
        direction: str,
        *,
        display_name: Optional[str] = None,
        is_reciprocal: Optional[bool] = None,
        followed_by_bot: Optional[bool] = None,
        unfollowed: bool = False,
        source: Optional[str] = None,
    ) -> None:
        """Primary upsert into the unified `social_graph_sync` table.

        The unified table is now the source of truth; the legacy per-side tables were
        dropped. Exceptions are not caught here:
        the caller handles the error and
        renvoie un statut "error".
        """
        unfollowed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if unfollowed else None
        self.execute(
            """INSERT INTO social_graph_sync
                   (platform, account_id, username, direction, display_name,
                    is_reciprocal, followed_by_bot, unfollowed_at, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(platform, account_id, username, direction) DO UPDATE SET
                   display_name = COALESCE(NULLIF(excluded.display_name, ''), social_graph_sync.display_name),
                   is_reciprocal = COALESCE(excluded.is_reciprocal, social_graph_sync.is_reciprocal),
                   followed_by_bot = COALESCE(excluded.followed_by_bot, social_graph_sync.followed_by_bot),
                   unfollowed_at = COALESCE(excluded.unfollowed_at, social_graph_sync.unfollowed_at),
                   source = COALESCE(NULLIF(excluded.source, ''), social_graph_sync.source),
                   last_seen_at = datetime('now')""",
            (
                self.platform,
                account_id,
                username,
                direction,
                display_name,
                None if is_reciprocal is None else int(is_reciprocal),
                None if followed_by_bot is None else int(followed_by_bot),
                unfollowed_at,
                source,
            ),
        )

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
                "SELECT 1 FROM social_graph_sync "
                "WHERE platform = ? AND account_id = ? AND username = ? COLLATE NOCASE AND direction = 'following'",
                (self.platform, account_id, username),
            )
            self._upsert_social_graph(account_id, username, "following",
                                      display_name=display_name, followed_by_bot=followed_by_bot, source=source)
            return "updated" if existing else "new"
        except Exception as exc:
            logger.debug(f"Error in upsert_following for @{username}: {exc}")
            return "error"

    def get_active_following_usernames(self, account_id: int) -> set[str]:
        if not account_id:
            return set()

        try:
            rows = self.query_orm_first(
                "SELECT username FROM social_graph_sync "
                "WHERE platform = ? AND account_id = ? AND direction = 'following' AND unfollowed_at IS NULL",
                (self.platform, account_id),
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
            self._upsert_social_graph(account_id, username, "following", is_reciprocal=is_follower_back)
        except Exception as exc:
            logger.debug(f"Error updating follower-back flag for @{username}: {exc}")

    def mark_unfollowed(self, username: str, account_id: int) -> None:
        if not account_id:
            return

        try:
            self._upsert_social_graph(account_id, username, "following", unfollowed=True)
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
                "SELECT 1 FROM social_graph_sync "
                "WHERE platform = ? AND account_id = ? AND username = ? COLLATE NOCASE AND direction = 'follower'",
                (self.platform, account_id, username),
            )
            self._upsert_social_graph(account_id, username, "follower",
                                      display_name=display_name, is_reciprocal=is_following_back, source=source)
            return "updated" if existing else "new"
        except Exception as exc:
            logger.debug(f"Error in upsert_follower for @{username}: {exc}")
            return "error"

    def get_follower_usernames(self, account_id: int) -> set[str]:
        if not account_id:
            return set()

        try:
            rows = self.query_orm_first(
                "SELECT username FROM social_graph_sync "
                "WHERE platform = ? AND account_id = ? AND direction = 'follower'",
                (self.platform, account_id),
            )
            return {row["username"].lower() for row in rows}
        except Exception as exc:
            logger.debug(f"Error in get_follower_usernames: {exc}")
            return set()
