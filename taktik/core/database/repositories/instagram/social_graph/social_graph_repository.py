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
from typing import Optional, Set

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

    def bot_followed_usernames(self, account_id: int) -> Set[str]:
        """Every handle this account ever followed successfully, lowercased: what
        `has_bot_follow_record` answers for one handle, read once for a whole list sync."""
        if not account_id:
            return set()
        rows = self.query_orm_first(
            """SELECT DISTINCT sp.username AS username FROM interactions i
               JOIN social_profiles sp ON sp.legacy_profile_id = i.profile_id AND sp.platform = i.platform
               WHERE i.platform = ? AND i.account_id = ? AND i.interaction_type = 'FOLLOW' AND i.success = 1""",
            (self.platform, account_id),
        )
        return {str(row["username"]).lower() for row in rows if row.get("username")}

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

    def get_days_since_first_seen_following(self, username: str, account_id: int) -> Optional[int]:
        """Full days since a following sync first saw this account in the CURRENT following, or None.

        The other half of a follow date, the half `get_days_since_follow` cannot give: an account
        followed by hand has no FOLLOW interaction, but a sync of the following list saw it on a
        known day, and it was followed on that day or before. The Instagram unfollow dates a follow
        the same way (`candidates._follow_date`: the bot's follow, else the first sighting). None
        when no sync has seen it, or when its row is closed (unfollowed).
        """
        if not account_id or not username:
            return None
        try:
            row = self.query_one_orm_first(
                "SELECT first_seen_at FROM social_graph_sync "
                "WHERE platform = ? AND account_id = ? AND username = ? COLLATE NOCASE "
                "AND direction = 'following' AND unfollowed_at IS NULL",
                (self.platform, account_id, username),
            )
            if not row or not row["first_seen_at"]:
                return None
            first_seen = datetime.fromisoformat(str(row["first_seen_at"]))
            return max(0, (datetime.now() - first_seen).days)
        except Exception as exc:
            logger.debug(f"Error getting the first sighting of @{username}: {exc}")
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
                "SELECT unfollowed_at, source FROM social_graph_sync "
                "WHERE platform = ? AND account_id = ? AND username = ? COLLATE NOCASE AND direction = 'following'",
                (self.platform, account_id, username),
            )
            bot_follow = source == "bot_follow"
            reopening = existing is not None and existing[0] is not None
            # A row reopened by a sync keeps its "refollow" mark until the bot itself follows the
            # account: the next syncs would otherwise overwrite it, and the old bot follow would
            # count again for a follow the bot did not make (see `list_active_followings`).
            keep_mark = existing is not None and existing[1] == "refollow" and not bot_follow
            self._upsert_social_graph(account_id, username, "following",
                                      display_name=display_name, followed_by_bot=followed_by_bot,
                                      source=None if keep_mark else source)
            if reopening:
                # Seen in the following list again, or followed again: followed NOW, a new
                # following episode that starts today. An earlier unfollow is history (the upsert's
                # COALESCE would keep `unfollowed_at`, and the account stayed "unfollowed" forever).
                # Not followed by the bot this time unless the bot just did it: marked "refollow",
                # so only a bot FOLLOW of this new episode makes it the bot's again.
                self.execute(
                    "UPDATE social_graph_sync SET unfollowed_at = NULL, first_seen_at = datetime('now'), "
                    "source = ? "
                    "WHERE platform = ? AND account_id = ? AND username = ? COLLATE NOCASE "
                    "AND direction = 'following' AND unfollowed_at IS NOT NULL",
                    ("bot_follow" if bot_follow else "refollow", self.platform, account_id, username),
                )
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

    def list_active_followings(self, account_id: int) -> list:
        """The active followings with who followed them and when: the unfollow candidates' source.

        One row per account followed (`unfollowed_at` empty): `username`, `first_seen_at` (when the
        current following episode was first seen) and `last_bot_follow_at` (the bot's last
        successful FOLLOW of that profile, from `interactions`, empty for a follow made by hand).
        Read live from `interactions` rather than from the `followed_by_bot` flag, which is only as
        fresh as the last sync that wrote it.

        A bot FOLLOW counts only for the CURRENT episode: it must be later than the account's last
        successful UNFOLLOW by the same account (same clock), and, on a row a sync reopened
        (`source = 'refollow'`, a re-follow the bot did not make), later than the reopening.
        Without that, an account the bot followed in August and unfollowed, then followed again by
        hand in September, passed for the bot's, 50 days old (review of 2026-09-24). The reopening
        is stamped in UTC and interactions in local time: 14 hours of slack cover every offset.
        """
        if not account_id:
            return []
        try:
            return self.query_orm_first(
                """WITH follows AS (
                       SELECT lower(p.username) AS uname, MAX(i.interaction_time) AS at
                         FROM interactions i
                         JOIN social_profiles p ON p.legacy_profile_id = i.profile_id
                        WHERE i.platform = ? AND p.platform = ? AND i.account_id = ?
                          AND i.interaction_type = 'FOLLOW' AND i.success = 1
                        GROUP BY lower(p.username)
                   ), unfollows AS (
                       SELECT lower(p.username) AS uname, MAX(i.interaction_time) AS at
                         FROM interactions i
                         JOIN social_profiles p ON p.legacy_profile_id = i.profile_id
                        WHERE i.platform = ? AND p.platform = ? AND i.account_id = ?
                          AND i.interaction_type = 'UNFOLLOW' AND i.success = 1
                        GROUP BY lower(p.username)
                   )
                   SELECT s.username AS username,
                          s.first_seen_at AS first_seen_at,
                          CASE
                            WHEN f.at IS NULL THEN NULL
                            WHEN u.at IS NOT NULL AND julianday(f.at) <= julianday(u.at) THEN NULL
                            WHEN s.source = 'refollow'
                             AND julianday(f.at) < julianday(s.first_seen_at) - 14.0 / 24.0 THEN NULL
                            ELSE f.at
                          END AS last_bot_follow_at
                     FROM social_graph_sync s
                     LEFT JOIN follows f ON f.uname = lower(s.username)
                     LEFT JOIN unfollows u ON u.uname = lower(s.username)
                    WHERE s.platform = ? AND s.account_id = ?
                      AND s.direction = 'following' AND s.unfollowed_at IS NULL""",
                (self.platform, self.platform, account_id,
                 self.platform, self.platform, account_id,
                 self.platform, account_id),
            )
        except Exception as exc:
            logger.debug(f"Error in list_active_followings: {exc}")
            return []

    def set_followings_reciprocity(self, account_id: int, follower_usernames) -> int:
        """After a COMPLETE read of the followers list: every active following is reciprocal
        (1) when it was seen among the followers, else not (0). Returns the rows written.

        Nothing wrote `is_reciprocal` on the following rows since the fans category stopped
        deducing it (U6), and the page's mutual / non-follower counts froze (review of
        2026-09-24). Call it only with a proven-complete read: absence means "no" only then.
        """
        if not account_id:
            return 0
        followers = {str(name).lower() for name in (follower_usernames or ())}
        try:
            rows = self.query(
                "SELECT username FROM social_graph_sync "
                "WHERE platform = ? AND account_id = ? AND direction = 'following' AND unfollowed_at IS NULL",
                (self.platform, account_id),
            )
            updates = [(1 if row[0].lower() in followers else 0, self.platform, account_id, row[0])
                       for row in rows]
            if not updates:
                return 0
            return self.execute_many(
                "UPDATE social_graph_sync SET is_reciprocal = ? "
                "WHERE platform = ? AND account_id = ? AND username = ? AND direction = 'following'",
                updates,
            )
        except Exception as exc:
            logger.debug(f"Error in set_followings_reciprocity: {exc}")
            return 0

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
