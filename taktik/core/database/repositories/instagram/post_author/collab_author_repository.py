"""Pseudo columns holding the author line of a collaboration post instead of one handle.

A post in collaboration names several accounts on its author line: "a et b", "a and b",
"a et 2 autres personnes". Before the extraction kept only the first handle
(`username_from_author_header`), that line was stored whole where one handle was expected: in the
hashtag post memory, and as the username of the profile a like was filed under, a profile nobody
can open.

The repair files each row under the first handle, as the fixed extraction does today:

- `processed_hashtag_posts`: the row takes the first handle. Left as it is, it no longer matches
  the key the run now builds for that post, and the 7-day guard lets the post be worked again. When
  a row already files the same post under that handle, the older of the two goes.
- a phantom profile of `social_profiles`: the interactions this device wrote under it move to the
  first handle's profile when that profile exists, and the phantom is MARKED unreachable, never
  deleted. The mark is an update, so it travels through the sync; a delete would not, and the
  other installs would hand the row back.

The other pseudo columns are only counted. Notification actors stay as they are: an aggregated
notification ("a and b liked ...") names several people on purpose, and its dedup hash is built
on that line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from taktik.core.shared.actions.utils import ActionUtils

from ..._base.base_repository import BaseRepository
from ..profile.profile_repository import MARK_UNREACHABLE_SQL


# The conjunctions of the languages the bot reads Instagram in (`ui/selectors/locales`). The
# extraction needs none, the first word being the author; a repair of stored values does, because
# other text with a space ("Send message") sits in the same columns and is no collaboration.
_CONJUNCTIONS = ("et", "and")

_COLLAB_LINE = re.compile(
    r"@?(?P<first>\S+)\s+(?:%s)\s+(?:@?(?P<second>\S+)|\d+\s+\S.*)" % "|".join(_CONJUNCTIONS),
    re.IGNORECASE | re.DOTALL,
)

# SQL prefilter: the separators seen in those lines (space, no-break space, narrow no-break space).
_HAS_SEPARATOR_GLOB = "*[ \u00a0\u202f\t]*"

# Pseudo columns counted, never written by this repair.
COUNTED_ONLY = (
    ("interactions", "target_username"),
    ("posted_comments", "post_author"),
    ("posted_comments", "target_username"),
    ("post_analysis", "post_author"),
    ("notifications", "actor_username"),
)


def _is_handle(word: str) -> bool:
    """A handle as it stands, the rule `username_from_author_header` applies to the first word."""
    return word == ActionUtils.clean_username(word) and ActionUtils.is_valid_username(
        word, min_length=1, max_length=30
    )


def collab_first_author(value: Optional[str]) -> Optional[str]:
    """The first handle of a stored collaboration author line; None for anything else."""
    match = _COLLAB_LINE.fullmatch((value or "").strip())
    if not match:
        return None
    first = match.group("first").lower()
    second = match.group("second")
    if not _is_handle(first):
        return None
    if second is not None and not _is_handle(second.lstrip("@").lower()):
        return None
    return first


@dataclass(frozen=True)
class HashtagPostFix:
    row_id: int
    account_id: int
    hashtag: str
    stored: str
    author: str
    processed_at: Optional[str]
    drop: bool = False
    replaces_id: Optional[int] = None


@dataclass(frozen=True)
class PhantomProfileFix:
    row_id: int
    profile_id: Optional[int]
    stored: str
    author: str
    author_profile_id: Optional[int]
    own_interactions: int
    already_marked: bool

    @property
    def moves_interactions(self) -> bool:
        return self.author_profile_id is not None and self.own_interactions > 0


@dataclass
class CollabAuthorPlan:
    hashtag_posts: List[HashtagPostFix] = field(default_factory=list)
    phantom_profiles: List[PhantomProfileFix] = field(default_factory=list)
    counted: Dict[str, int] = field(default_factory=dict)

    @property
    def has_work(self) -> bool:
        return bool(self.hashtag_posts or self.phantom_profiles)


class CollabAuthorRepository(BaseRepository):
    """Finds and repairs the collaboration author lines stored as one pseudo."""

    def plan(self) -> CollabAuthorPlan:
        """What `apply` would change, read only."""
        return CollabAuthorPlan(
            hashtag_posts=self._plan_hashtag_posts(),
            phantom_profiles=self._plan_phantom_profiles(),
            counted=self._count_elsewhere(),
        )

    def apply(self) -> CollabAuthorPlan:
        """Plan again under the write lock and apply it in one transaction; returns what was done."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            plan = self.plan()
            self._apply_hashtag_posts(plan.hashtag_posts)
            self._apply_phantom_profiles(plan.phantom_profiles)
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return plan

    # processed_hashtag_posts

    def _plan_hashtag_posts(self) -> List[HashtagPostFix]:
        if not self.column_exists("processed_hashtag_posts", "post_author"):
            return []
        rows = self.query(
            "SELECT id, account_id, hashtag, post_author, post_caption_hash, processed_at "
            "FROM processed_hashtag_posts WHERE post_author GLOB ? ORDER BY id",
            (_HAS_SEPARATOR_GLOB,),
        )
        holders: Dict[Tuple, Tuple[int, Optional[str]]] = {}
        fixes: List[HashtagPostFix] = []
        for row in rows:
            author = collab_first_author(row["post_author"])
            if not author:
                continue
            fix = dict(
                row_id=row["id"], account_id=row["account_id"], hashtag=row["hashtag"],
                stored=row["post_author"], author=author, processed_at=row["processed_at"],
            )
            # UNIQUE(account_id, hashtag, post_author, post_caption_hash) only binds a real hash.
            if row["post_caption_hash"] is None:
                fixes.append(HashtagPostFix(**fix))
                continue
            key = (row["account_id"], row["hashtag"], author, row["post_caption_hash"])
            holder = holders.get(key) or self._hashtag_post_holder(key, row["id"])
            if holder and (holder[1] or "") >= (row["processed_at"] or ""):
                fixes.append(HashtagPostFix(**fix, drop=True))
                continue
            fixes.append(HashtagPostFix(**fix, replaces_id=holder[0] if holder else None))
            holders[key] = (row["id"], row["processed_at"])
        return fixes

    def _hashtag_post_holder(self, key: Tuple, exclude_id: int) -> Optional[Tuple[int, Optional[str]]]:
        row = self.query_one(
            "SELECT id, processed_at FROM processed_hashtag_posts "
            "WHERE account_id = ? AND hashtag = ? AND post_author = ? AND post_caption_hash = ? "
            "AND id != ?",
            (*key, exclude_id),
        )
        return (row["id"], row["processed_at"]) if row else None

    def _apply_hashtag_posts(self, fixes: List[HashtagPostFix]) -> None:
        for fix in fixes:
            if fix.drop:
                self.conn.execute("DELETE FROM processed_hashtag_posts WHERE id = ?", (fix.row_id,))
                continue
            if fix.replaces_id is not None:
                self.conn.execute("DELETE FROM processed_hashtag_posts WHERE id = ?", (fix.replaces_id,))
            self.conn.execute(
                "UPDATE processed_hashtag_posts SET post_author = ? WHERE id = ?",
                (fix.author, fix.row_id),
            )

    # social_profiles + interactions

    def _own_interactions_clause(self) -> str:
        """Only the rows this device wrote: a pulled row's profile_id is another device's id."""
        if self.column_exists("interactions", "origin_device_id") and self.column_exists(
            "device_identity", "device_id"
        ):
            return " AND origin_device_id = (SELECT device_id FROM device_identity WHERE id = 1)"
        return ""

    def _plan_phantom_profiles(self) -> List[PhantomProfileFix]:
        if not self.column_exists("social_profiles", "username"):
            return []
        has_interactions = self.column_exists("interactions", "profile_id")
        own = self._own_interactions_clause() if has_interactions else ""
        rows = self.query(
            "SELECT id, legacy_profile_id, username, unreachable_at FROM social_profiles "
            "WHERE platform = 'instagram' AND username GLOB ? ORDER BY id",
            (_HAS_SEPARATOR_GLOB,),
        )
        fixes: List[PhantomProfileFix] = []
        for row in rows:
            author = collab_first_author(row["username"])
            if not author:
                continue
            target = self.query_one(
                "SELECT legacy_profile_id FROM social_profiles "
                "WHERE platform = 'instagram' AND username = ?",
                (author,),
            )
            own_count = 0
            if has_interactions and row["legacy_profile_id"] is not None:
                own_count = self.query_one(
                    "SELECT COUNT(*) AS n FROM interactions "
                    f"WHERE platform = 'instagram' AND profile_id = ?{own}",
                    (row["legacy_profile_id"],),
                )["n"]
            fix = PhantomProfileFix(
                row_id=row["id"],
                profile_id=row["legacy_profile_id"],
                stored=row["username"],
                author=author,
                author_profile_id=target["legacy_profile_id"] if target else None,
                own_interactions=own_count,
                already_marked=row["unreachable_at"] is not None,
            )
            if fix.already_marked and not fix.moves_interactions:
                continue
            fixes.append(fix)
        return fixes

    def _apply_phantom_profiles(self, fixes: List[PhantomProfileFix]) -> None:
        own = self._own_interactions_clause()
        with_target = self.column_exists("interactions", "target_username")
        for fix in fixes:
            if fix.moves_interactions:
                if with_target:
                    # NULL stays NULL: the sync fills it from the profile the row now points at.
                    self.conn.execute(
                        "UPDATE interactions SET profile_id = ?, "
                        "target_username = CASE WHEN target_username IS NULL THEN NULL ELSE ? END "
                        f"WHERE platform = 'instagram' AND profile_id = ?{own}",
                        (fix.author_profile_id, fix.author, fix.profile_id),
                    )
                else:
                    self.conn.execute(
                        "UPDATE interactions SET profile_id = ? "
                        f"WHERE platform = 'instagram' AND profile_id = ?{own}",
                        (fix.author_profile_id, fix.profile_id),
                    )
            if not fix.already_marked:
                self.conn.execute(MARK_UNREACHABLE_SQL, ("instagram", fix.stored))

    # counted only

    def _count_elsewhere(self) -> Dict[str, int]:
        counted: Dict[str, int] = {}
        for table, column in COUNTED_ONLY:
            if not self.column_exists(table, column):
                continue
            rows = self.query(
                f'SELECT "{column}" AS value FROM "{table}" WHERE "{column}" GLOB ?',
                (_HAS_SEPARATOR_GLOB,),
            )
            counted[f"{table}.{column}"] = sum(1 for row in rows if collab_first_author(row["value"]))
        return counted


__all__ = [
    "COUNTED_ONLY",
    "CollabAuthorPlan",
    "CollabAuthorRepository",
    "HashtagPostFix",
    "PhantomProfileFix",
    "collab_first_author",
]
