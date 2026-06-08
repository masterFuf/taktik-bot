"""Repository for Instagram follow graph sync tables and follow-history lookups."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from loguru import logger

from ..._base.base_repository import BaseRepository


class SocialGraphRepository(BaseRepository):
    """Read/write access for the unified `social_graph_sync` follow graph + follow lookups."""

    def has_bot_follow_record(self, username: str, account_id: int) -> bool:
        if not account_id:
            return False

        try:
            row = self.query_one_orm_first(
                "SELECT profile_id FROM instagram_profiles WHERE username = ? COLLATE NOCASE",
                (username,),
            )
            if not row:
                return False

            interaction = self.query_one_orm_first(
                """SELECT 1 FROM interactions
                   WHERE platform = 'instagram' AND account_id = ? AND profile_id = ? AND interaction_type = 'FOLLOW' AND success = 1
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
            row = self.query_one_orm_first(
                "SELECT profile_id FROM instagram_profiles WHERE username = ? COLLATE NOCASE",
                (username,),
            )
            if not row:
                return None

            follow = self.query_one_orm_first(
                """SELECT interaction_time FROM interactions
                   WHERE platform = 'instagram' AND account_id = ? AND profile_id = ? AND interaction_type = 'FOLLOW' AND success = 1
                   ORDER BY interaction_time DESC LIMIT 1""",
                (account_id, row["profile_id"]),
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

        Restructuring Vague B : `social_graph_sync` est desormais la source de
        verite (les tables legacy `following_sync`/`followers_sync` ont ete
        droppees). Ne capture pas les exceptions : l'appelant gere l'erreur et
        renvoie un statut "error".
        """
        unfollowed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if unfollowed else None
        self.execute(
            """INSERT INTO social_graph_sync
                   (platform, account_id, username, direction, display_name,
                    is_reciprocal, followed_by_bot, unfollowed_at, source)
               VALUES ('instagram', ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(platform, account_id, username, direction) DO UPDATE SET
                   display_name = COALESCE(NULLIF(excluded.display_name, ''), social_graph_sync.display_name),
                   is_reciprocal = COALESCE(excluded.is_reciprocal, social_graph_sync.is_reciprocal),
                   followed_by_bot = COALESCE(excluded.followed_by_bot, social_graph_sync.followed_by_bot),
                   unfollowed_at = COALESCE(excluded.unfollowed_at, social_graph_sync.unfollowed_at),
                   source = COALESCE(NULLIF(excluded.source, ''), social_graph_sync.source),
                   last_seen_at = datetime('now')""",
            (
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
                "WHERE platform = 'instagram' AND account_id = ? AND username = ? COLLATE NOCASE AND direction = 'following'",
                (account_id, username),
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
                "WHERE platform = 'instagram' AND account_id = ? AND direction = 'following' AND unfollowed_at IS NULL",
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
                "WHERE platform = 'instagram' AND account_id = ? AND username = ? COLLATE NOCASE AND direction = 'follower'",
                (account_id, username),
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
                "WHERE platform = 'instagram' AND account_id = ? AND direction = 'follower'",
                (account_id,),
            )
            return {row["username"].lower() for row in rows}
        except Exception as exc:
            logger.debug(f"Error in get_follower_usernames: {exc}")
            return set()
