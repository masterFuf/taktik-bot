"""Stats snapshots a scraping run wrote twice for one reading of a profile.

A scraping run saved each kept profile as soon as it read it, then saved the whole list again at
the end; each save wrote a `profile_stats_history` snapshot. The run now saves a profile once.
This removes the second snapshot of the pairs written before, and only when all of this holds:

- both snapshots lie inside one COMPLETED Instagram scraping run (its start to its end; the final
  save happens before the run is closed), and that run links the profile (`scraped_profiles`);
- the run holds exactly these two snapshots of the profile;
- the second is the exact double of the first: every column equal, the row id, its sync key and
  its time apart;
- no other run that links the profile covers either snapshot (two runs at once on two devices).

Anything else is counted, listed and left as it is: two snapshots that differ are two readings.

Local only: the sync pushes `profile_stats_history` as append-only rows and carries no deletion, so
a double already pushed stays in the remote base.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from taktik.core.database.repositories._base.base_repository import BaseRepository

#: Columns that are no part of a reading: what tells two rows apart, not what they say.
NOT_THE_READING = ("id", "sync_id", "recorded_at")

#: Bounds that stand for a run nobody closed, and for a run without a start: it covers that side.
_OPEN_END = "9999-12-31 23:59:59"
_NO_START = "0000-01-01 00:00:00"

_SNAPSHOTS_IN_RUNS_SQL = """
    SELECT ss.scraping_id,
           sp.profile_id,
           p.username AS profile_username,
           datetime(h.recorded_at) AS taken_at,
           h.*
      FROM scraping_sessions ss
      JOIN scraped_profiles sp
        ON sp.scraping_id = ss.scraping_id AND COALESCE(sp.platform, 'instagram') = 'instagram'
      JOIN profile_stats_history h
        ON h.profile_id = sp.profile_id
       AND datetime(h.recorded_at) BETWEEN datetime(ss.start_time) AND datetime(ss.end_time)
      LEFT JOIN social_profiles p
        ON p.platform = 'instagram' AND p.legacy_profile_id = sp.profile_id
     WHERE COALESCE(ss.platform, 'instagram') = 'instagram'
       AND upper(ss.status) = 'COMPLETED'
       AND ss.end_time IS NOT NULL
     ORDER BY ss.scraping_id, sp.profile_id, datetime(h.recorded_at), h.id
"""

_RUN_WINDOWS_SQL = f"""
    SELECT sp.profile_id,
           ss.scraping_id,
           COALESCE(datetime(ss.start_time), '{_NO_START}') AS run_start,
           COALESCE(datetime(ss.end_time), '{_OPEN_END}') AS run_end
      FROM scraped_profiles sp
      JOIN scraping_sessions ss ON ss.scraping_id = sp.scraping_id
     WHERE COALESCE(sp.platform, 'instagram') = 'instagram'
       AND COALESCE(ss.platform, 'instagram') = 'instagram'
"""


@dataclass(frozen=True)
class SnapshotPair:
    """Two snapshots of one profile inside one run, in the order they were taken."""
    scraping_id: int
    profile_id: int
    username: Optional[str]
    first_id: int
    first_at: str
    second_id: int
    second_at: str
    first_row: Tuple[Tuple[str, object], ...]
    second_row: Tuple[Tuple[str, object], ...]
    other_runs: Tuple[int, ...] = ()

    @property
    def is_exact_double(self) -> bool:
        first, second = dict(self.first_row), dict(self.second_row)
        return all(first[column] == second[column] for column in first if column not in NOT_THE_READING)

    def counters(self, which: str = "first") -> str:
        row = dict(self.first_row if which == "first" else self.second_row)
        return f"{row.get('followers_count')}/{row.get('following_count')}/{row.get('posts_count')}"


@dataclass(frozen=True)
class CrowdedRun:
    """More than two snapshots of one profile inside one run: no single double to pick."""
    scraping_id: int
    profile_id: int
    username: Optional[str]
    snapshot_ids: Tuple[int, ...]


@dataclass
class StatsDoublePlan:
    doubles: List[SnapshotPair] = field(default_factory=list)
    different: List[SnapshotPair] = field(default_factory=list)
    shared: List[SnapshotPair] = field(default_factory=list)
    crowded: List[CrowdedRun] = field(default_factory=list)

    @property
    def has_work(self) -> bool:
        return bool(self.doubles)


class StatsSnapshotDoubleRepository(BaseRepository):
    """Finds the snapshots a run wrote twice for one reading, and removes the second."""

    def plan(self) -> StatsDoublePlan:
        """What `write` would remove, read only."""
        plan = StatsDoublePlan()
        by_run_and_profile: Dict[Tuple[int, int], list] = defaultdict(list)
        for row in self.query(_SNAPSHOTS_IN_RUNS_SQL):
            by_run_and_profile[(row["scraping_id"], row["profile_id"])].append(row)
        if not by_run_and_profile:
            return plan

        windows = self._run_windows()
        columns = self._snapshot_columns()
        for (scraping_id, profile_id), snapshots in by_run_and_profile.items():
            username = snapshots[0]["profile_username"]
            if len(snapshots) == 1:
                continue
            if len(snapshots) > 2:
                plan.crowded.append(CrowdedRun(
                    scraping_id=scraping_id,
                    profile_id=profile_id,
                    username=username,
                    snapshot_ids=tuple(row["id"] for row in snapshots),
                ))
                continue
            first, second = snapshots
            others = tuple(
                other for other, start, end in windows.get(profile_id, ())
                if other != scraping_id and any(start <= row["taken_at"] <= end for row in snapshots)
            )
            pair = SnapshotPair(
                scraping_id=scraping_id,
                profile_id=profile_id,
                username=username,
                first_id=first["id"],
                first_at=first["taken_at"],
                second_id=second["id"],
                second_at=second["taken_at"],
                first_row=tuple((column, first[column]) for column in columns),
                second_row=tuple((column, second[column]) for column in columns),
                other_runs=others,
            )
            if not pair.is_exact_double:
                plan.different.append(pair)
            elif others:
                plan.shared.append(pair)
            else:
                plan.doubles.append(pair)
        return plan

    def write(self, plan: StatsDoublePlan) -> int:
        """Remove the second snapshot of each double; the caller holds the transaction."""
        for pair in plan.doubles:
            # conn.execute, not self.execute: that one commits, and the caller holds the transaction.
            cursor = self.conn.execute("DELETE FROM profile_stats_history WHERE id = ?", (pair.second_id,))
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"profile_stats_history {pair.second_id}: {cursor.rowcount} ligne(s) retiree(s), 1 attendue"
                )
        return len(plan.doubles)

    def _run_windows(self) -> Dict[int, List[Tuple[int, str, str]]]:
        """Profile id -> every Instagram run that links it, as (run, start, end); a run nobody
        closed covers everything after its start."""
        windows: Dict[int, List[Tuple[int, str, str]]] = defaultdict(list)
        for row in self.query(_RUN_WINDOWS_SQL):
            windows[row["profile_id"]].append((row["scraping_id"], row["run_start"], row["run_end"]))
        return windows

    def _snapshot_columns(self) -> Tuple[str, ...]:
        """The snapshot's own columns, as this base has them (the joined ones left out)."""
        return tuple(info["name"] for info in self.query('PRAGMA table_info("profile_stats_history")'))


__all__ = [
    "CrowdedRun",
    "NOT_THE_READING",
    "SnapshotPair",
    "StatsDoublePlan",
    "StatsSnapshotDoubleRepository",
]
