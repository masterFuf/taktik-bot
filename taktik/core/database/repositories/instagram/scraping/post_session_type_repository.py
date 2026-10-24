"""Hashtag and post_url scraping sessions stored with the type of a follower scrape.

A hashtag or post_url run reads lists of posts (likers, commenters), never the followers of an
account. Its session row used to fall through to the writer's default type, 'followers'; the
writer now types it by the lists the run reads. This repairs the rows written before, from the
config each session saved: the caller hands the rule that reads that config back (the run's own
rule, owned by the workflow), so the type is never chosen here. A session the rule cannot decide
is listed and left as it is.

`updated_at` moves with the type: the sync carries a session row by that column.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Sequence, Tuple

from taktik.core.database.repositories._base.base_repository import BaseRepository

#: The type the writer gave every session it did not type itself.
OLD_DEFAULT_TYPE = "followers"

#: Reads a session's saved config back: (type, '') or (None, why it cannot decide).
TypeFromConfig = Callable[[str, Any], Tuple[Optional[str], str]]


@dataclass(frozen=True)
class PostSessionRow:
    scraping_id: int
    source_type: str
    source_name: str
    start_time: Optional[str]
    stored: str
    new_type: Optional[str] = None
    reason: str = ""


@dataclass
class PostSessionTypePlan:
    fixes: List[PostSessionRow] = field(default_factory=list)
    undecided: List[PostSessionRow] = field(default_factory=list)

    @property
    def has_work(self) -> bool:
        return bool(self.fixes)


class PostSessionTypeRepository(BaseRepository):
    """Finds the post sessions typed 'followers' and gives them the type their config says."""

    def plan(self, source_types: Sequence[str], type_from_config: TypeFromConfig) -> PostSessionTypePlan:
        """What `write` would change, read only."""
        plan = PostSessionTypePlan()
        if not source_types:
            return plan
        placeholders = ", ".join("?" for _ in source_types)
        rows = self.query(
            "SELECT scraping_id, source_type, source_name, start_time, config_used "
            "FROM scraping_sessions "
            "WHERE COALESCE(platform, 'instagram') = 'instagram' "
            f"AND source_type IN ({placeholders}) AND scraping_type = ? "
            "ORDER BY scraping_id",
            (*source_types, OLD_DEFAULT_TYPE),
        )
        for row in rows:
            new_type, reason = self._type_of(row["source_type"], row["config_used"], type_from_config)
            session = PostSessionRow(
                scraping_id=row["scraping_id"],
                source_type=row["source_type"],
                source_name=row["source_name"],
                start_time=row["start_time"],
                stored=OLD_DEFAULT_TYPE,
                new_type=new_type,
                reason=reason,
            )
            if new_type is None:
                plan.undecided.append(session)
            else:
                plan.fixes.append(session)
        return plan

    def write(self, plan: PostSessionTypePlan) -> int:
        """Give each session of the plan its type; the caller holds the transaction."""
        moves_updated_at = self.column_exists("scraping_sessions", "updated_at")
        sql = "UPDATE scraping_sessions SET scraping_type = ?"
        if moves_updated_at:
            sql += ", updated_at = datetime('now')"
        sql += " WHERE scraping_id = ? AND scraping_type = ?"
        for session in plan.fixes:
            # conn.execute, not self.execute: that one commits, and the caller holds the transaction.
            cursor = self.conn.execute(sql, (session.new_type, session.scraping_id, OLD_DEFAULT_TYPE))
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"scraping_sessions {session.scraping_id}: {cursor.rowcount} ligne(s) changee(s), 1 attendue"
                )
        return len(plan.fixes)

    @staticmethod
    def _type_of(source_type: str, raw_config: Optional[str],
                 type_from_config: TypeFromConfig) -> Tuple[Optional[str], str]:
        if not raw_config:
            return None, "aucune config enregistree"
        try:
            config = json.loads(raw_config)
        except ValueError as exc:
            return None, f"config enregistree illisible ({exc})"
        return type_from_config(source_type, config)


__all__ = [
    "OLD_DEFAULT_TYPE",
    "PostSessionRow",
    "PostSessionTypePlan",
    "PostSessionTypeRepository",
    "TypeFromConfig",
]
