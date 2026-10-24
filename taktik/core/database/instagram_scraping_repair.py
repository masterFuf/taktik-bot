"""Repair, in one transaction, two records the Instagram scraping runs wrote wrong.

- `scraping_sessions.scraping_type`: hashtag and post_url sessions stored as 'followers'
  (`PostSessionTypeRepository`);
- `profile_stats_history`: the second snapshot a run wrote for one reading of a profile
  (`StatsSnapshotDoubleRepository`).

The writers are fixed; this deals with the rows stored before. The type of a session is read back
from its saved config by the rule the caller hands over (the workflow's), never chosen here.
`plan` reads only; `apply` plans again under the write lock and writes both repairs in one
transaction, or nothing.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Sequence

from taktik.core.database.repositories.instagram.profile.stats_double_repository import (
    StatsDoublePlan,
    StatsSnapshotDoubleRepository,
)
from taktik.core.database.repositories.instagram.scraping.post_session_type_repository import (
    PostSessionTypePlan,
    PostSessionTypeRepository,
    TypeFromConfig,
)


@dataclass
class ScrapingRunRepairPlan:
    session_types: PostSessionTypePlan = field(default_factory=PostSessionTypePlan)
    stats_doubles: StatsDoublePlan = field(default_factory=StatsDoublePlan)

    @property
    def has_work(self) -> bool:
        return self.session_types.has_work or self.stats_doubles.has_work


class ScrapingRunRepair:
    """Both repairs over one connection; the transaction is held here."""

    def __init__(self, conn: sqlite3.Connection, post_source_types: Sequence[str],
                 type_from_config: TypeFromConfig):
        self._conn = conn
        self._post_source_types = tuple(post_source_types)
        self._type_from_config = type_from_config
        self._sessions = PostSessionTypeRepository(conn)
        self._snapshots = StatsSnapshotDoubleRepository(conn)

    def plan(self) -> ScrapingRunRepairPlan:
        """What `apply` would write, read only."""
        return ScrapingRunRepairPlan(
            session_types=self._sessions.plan(self._post_source_types, self._type_from_config),
            stats_doubles=self._snapshots.plan(),
        )

    def apply(self) -> ScrapingRunRepairPlan:
        """Plan again under the write lock, write both repairs, commit; on any error, roll back
        and raise. Returns what was written."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            plan = self.plan()
            self._sessions.write(plan.session_types)
            self._snapshots.write(plan.stats_doubles)
        except Exception:
            self._conn.rollback()
            raise
        self._conn.commit()
        return plan


__all__ = ["ScrapingRunRepair", "ScrapingRunRepairPlan"]
