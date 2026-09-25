"""Profiles whose pseudo no platform would register as a handle.

Seen in the base: button labels ("Send message", "Envoyer un message"), a handle followed by spaces
or holding control characters, a biography squeezed into one word, a TikTok display name. The
profile writers now refuse such a pseudo (`require_handle`); this repairs what was stored before.

Each row is MARKED unreachable, never deleted nor renamed. The Turso sync keys `social_profiles` on
(platform, username) and carries inserts and updates, not deletions: a deleted row stays on the
other installs and may come back on a pull, and a renamed one leaves its old key alive there. The
mark is an update and travels. What points at a row (qualification, scraping link, cached image)
is counted and left as it is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from taktik.core.shared.text import is_platform_handle

from .._base.base_repository import BaseRepository
from ..instagram.profile.profile_repository import MARK_UNREACHABLE_SQL

PLATFORMS = ("instagram", "tiktok")

# SQL prefilter only; `is_platform_handle` decides. Every row outside it is a handle by charset
# and within both platforms' length bounds.
_MAYBE_INVALID_SQL = (
    "SELECT id, platform, legacy_profile_id, username, created_at, unreachable_at "
    "FROM social_profiles WHERE platform = ? "
    "AND (username GLOB '*[^A-Za-z0-9._]*' OR length(username) NOT BETWEEN 2 AND 24) "
    "ORDER BY id"
)

# (table, column, key): what may point at a profile, by its per-platform id or by its pseudo.
# A table without a platform column only holds Instagram rows.
REFERENCES = (
    ("interactions", "profile_id", "id"),
    ("interactions", "target_username", "name"),
    ("scraped_profiles", "profile_id", "id"),
    ("filtered_profiles", "profile_id", "id"),
    ("filtered_profiles", "username", "name"),
    ("profile_qualification", "profile_id", "id"),
    ("profile_qualification", "username", "name"),
    ("media", "profile_id", "id"),
    ("media", "username", "name"),
    ("profile_stats_history", "profile_id", "id"),
    ("profile_following", "profile_id", "id"),
    ("profile_following", "following_username", "name"),
    ("notifications", "actor_profile_id", "id"),
    ("notifications", "actor_username", "name"),
    ("dm_threads", "partner_profile_id", "id"),
    ("dm_threads", "partner_username", "name"),
    ("sent_dms", "recipient_username", "name"),
    ("posted_comments", "target_username", "name"),
)


@dataclass(frozen=True)
class InvalidHandleProfile:
    row_id: int
    platform: str
    profile_id: Optional[int]
    stored: str
    created_at: Optional[str]
    already_marked: bool
    references: Tuple[Tuple[str, int], ...] = ()


@dataclass
class InvalidHandlePlan:
    profiles: List[InvalidHandleProfile] = field(default_factory=list)

    @property
    def to_mark(self) -> List[InvalidHandleProfile]:
        return [profile for profile in self.profiles if not profile.already_marked]

    @property
    def has_work(self) -> bool:
        return bool(self.to_mark)


class InvalidHandleRepository(BaseRepository):
    """Finds the profiles stored under a pseudo that is no handle, and marks them unreachable."""

    def plan(self) -> InvalidHandlePlan:
        """What `apply` would mark, read only."""
        if not self.column_exists("social_profiles", "unreachable_at"):
            return InvalidHandlePlan()
        profiles: List[InvalidHandleProfile] = []
        for platform in PLATFORMS:
            for row in self.query(_MAYBE_INVALID_SQL, (platform,)):
                if is_platform_handle(row["username"], platform):
                    continue
                profiles.append(InvalidHandleProfile(
                    row_id=row["id"],
                    platform=platform,
                    profile_id=row["legacy_profile_id"],
                    stored=row["username"],
                    created_at=row["created_at"],
                    already_marked=row["unreachable_at"] is not None,
                    references=self._references(platform, row["legacy_profile_id"], row["username"]),
                ))
        return InvalidHandlePlan(profiles=profiles)

    def apply(self) -> InvalidHandlePlan:
        """Plan again under the write lock and mark in one transaction; returns what was found."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            plan = self.plan()
            for profile in plan.to_mark:
                self.conn.execute(MARK_UNREACHABLE_SQL, (profile.platform, profile.stored))
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return plan

    def _references(self, platform: str, profile_id: Optional[int], username: str) -> Tuple[Tuple[str, int], ...]:
        found = []
        for table, column, key in REFERENCES:
            if not self.column_exists(table, column):
                continue
            value = profile_id if key == "id" else username
            if value is None:
                continue
            sql = f'SELECT COUNT(*) AS n FROM "{table}" WHERE "{column}" = ?'
            params: Tuple = (value,)
            if self.column_exists(table, "platform"):
                sql += " AND platform = ?"
                params += (platform,)
            elif platform != "instagram":
                continue
            if (table, key) == ("interactions", "id"):
                sql += self._own_rows_clause()
            count = self.query_one(sql, params)["n"]
            if count:
                found.append((f"{table}.{column}", count))
        return tuple(found)

    def _own_rows_clause(self) -> str:
        """A pulled interaction carries its own device's profile id, which means another profile here."""
        if self.column_exists("interactions", "origin_device_id") and self.column_exists(
            "device_identity", "device_id"
        ):
            return " AND origin_device_id = (SELECT device_id FROM device_identity WHERE id = 1)"
        return ""


__all__ = [
    "InvalidHandlePlan",
    "InvalidHandleProfile",
    "InvalidHandleRepository",
    "PLATFORMS",
    "REFERENCES",
]
