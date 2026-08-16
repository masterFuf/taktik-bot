"""The life of a scraping run, and the two things easy to get wrong about it.

Against a real SQLite database, because the parts that matter are what SQLite does: the
`sync_id` generated at INSERT, the row counting of the orphan cleanup, and the timestamps
the durations are computed from.

Two traps are pinned here:

`sync_id` must never be NULL. NULL is distinct from NULL on a primary key, so the Turso push
re-inserts a NULL-keyed row on every cycle — the session multiplies instead of updating.

Durations are UTC deltas. `start_time` comes from SQLite's `datetime('now')`, which is UTC;
reading it as local time adds the machine's offset to every duration ever recorded.
"""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from taktik.core.database.repositories.instagram.scraping import (
    ScrapingSessionRepository,
    parse_stored_utc,
)


@pytest.fixture
def repo():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE scraping_sessions (
            scraping_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            scraping_type TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_name TEXT NOT NULL,
            max_profiles INTEGER,
            export_csv INTEGER DEFAULT 0,
            save_to_db INTEGER DEFAULT 1,
            config_used TEXT,
            total_scraped INTEGER DEFAULT 0,
            csv_path TEXT,
            status TEXT DEFAULT 'IN_PROGRESS',
            error_message TEXT,
            duration_seconds INTEGER,
            start_time TEXT DEFAULT (datetime('now')),
            end_time TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            sync_id TEXT
        )
    """)
    conn.commit()
    return ScrapingSessionRepository(conn)


def test_a_new_session_starts_in_progress(repo):
    sid = repo.create("followers", "TARGET", "@someone", max_profiles=200)
    assert isinstance(sid, int)

    session = repo.get(sid)
    assert session["status"] == "IN_PROGRESS"
    assert session["source_name"] == "@someone"
    assert session["max_profiles"] == 200


def test_every_session_gets_a_sync_id(repo):
    """A NULL sync_id makes the cross-device push re-insert the row forever."""
    first = repo.get(repo.create("followers", "TARGET", "@a"))
    second = repo.get(repo.create("followers", "TARGET", "@b"))

    assert first["sync_id"], "no sync_id: this row would be re-inserted on every push"
    assert len(first["sync_id"]) == 32
    assert first["sync_id"] != second["sync_id"]


def test_the_flags_come_back_as_booleans(repo):
    """SQLite stores 0/1; callers branch on these as booleans."""
    session = repo.get(repo.create("followers", "TARGET", "@a",
                                   export_csv=True, save_to_db=False))
    assert session["export_csv"] is True
    assert session["save_to_db"] is False


def test_progress_is_saved_mid_run(repo):
    """A crash must still leave a truthful count behind."""
    sid = repo.create("followers", "TARGET", "@a")
    repo.update_count(sid, 42)
    assert repo.get(sid)["total_scraped"] == 42


def test_an_update_ignores_columns_it_does_not_own(repo):
    """The update is built by concatenation, so the column names come from the allowlist."""
    sid = repo.create("followers", "TARGET", "@a")
    assert repo.update(sid, status="COMPLETED", nonsense="x", scraping_type="hacked") is True

    session = repo.get(sid)
    assert session["status"] == "COMPLETED"
    assert session["scraping_type"] == "followers"   # untouched


def test_an_empty_update_is_not_a_failure(repo):
    sid = repo.create("followers", "TARGET", "@a")
    assert repo.update(sid) is True


def test_completing_a_run_records_a_duration(repo):
    sid = repo.create("followers", "TARGET", "@a")
    started = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    repo.conn.execute("UPDATE scraping_sessions SET start_time = ?", (started,))
    repo.conn.commit()

    assert repo.complete(sid, total_scraped=120, csv_path="/tmp/out.csv") is True
    session = repo.get(sid)
    assert session["status"] == "COMPLETED"
    assert session["total_scraped"] == 120
    assert 290 <= session["duration_seconds"] <= 310   # ~5 minutes, UTC delta


def test_a_completed_run_carrying_an_error_is_an_error(repo):
    sid = repo.create("followers", "TARGET", "@a")
    repo.complete(sid, total_scraped=3, error_message="device lost")

    session = repo.get(sid)
    assert session["status"] == "ERROR"
    assert session["error_message"] == "device lost"


def test_a_cancelled_run_is_not_a_failed_one(repo):
    """The operator stopping a run is a distinct outcome from a crash."""
    sid = repo.create("followers", "TARGET", "@a")
    assert repo.cancel(sid, total_scraped=7) is True

    session = repo.get(sid)
    assert session["status"] == "CANCELLED"
    assert session["total_scraped"] == 7


def test_finishing_an_unknown_session_reports_failure(repo):
    assert repo.complete(9999, total_scraped=1) is False
    assert repo.cancel(9999, total_scraped=1) is False


def test_orphans_are_closed_and_counted(repo):
    """A row still IN_PROGRESS at startup means the app died mid-run."""
    repo.create("followers", "TARGET", "@a")
    repo.create("followers", "TARGET", "@b")
    done = repo.create("followers", "TARGET", "@c")
    repo.complete(done, total_scraped=1)

    assert repo.cleanup_orphans() == 2
    assert repo.get(done)["status"] == "COMPLETED"      # untouched
    assert repo.cleanup_orphans() == 0                  # idempotent


def test_recent_sessions_can_be_narrowed_by_status(repo):
    a = repo.create("followers", "TARGET", "@a")
    repo.create("followers", "TARGET", "@b")
    repo.complete(a, total_scraped=5)

    assert len(repo.list_recent()) == 2
    completed = repo.list_recent(status="COMPLETED")
    assert [s["scraping_id"] for s in completed] == [a]


def test_stats_over_an_empty_window_read_as_zeros(repo):
    """COALESCE everywhere: the caller must not have to guard against None."""
    stats = repo.stats(days=7)
    assert stats["total_sessions"] == 0
    assert stats["total_profiles_scraped"] == 0
    assert stats["total_duration_seconds"] == 0


def test_stats_count_completed_and_failed_apart(repo):
    ok = repo.create("followers", "TARGET", "@a")
    ko = repo.create("followers", "TARGET", "@b")
    repo.complete(ok, total_scraped=10)
    repo.complete(ko, total_scraped=2, error_message="boom")

    stats = repo.stats(days=7)
    assert stats["total_sessions"] == 2
    assert stats["completed_sessions"] == 1
    assert stats["failed_sessions"] == 1
    assert stats["total_profiles_scraped"] == 12


@pytest.mark.parametrize("stored,expected_utc", [
    ("2026-08-15 10:00:00", datetime(2026, 8, 15, 10, tzinfo=timezone.utc)),
    ("2026-08-15T10:00:00Z", datetime(2026, 8, 15, 10, tzinfo=timezone.utc)),
    ("2026-08-15T10:00:00+00:00", datetime(2026, 8, 15, 10, tzinfo=timezone.utc)),
])
def test_a_naive_timestamp_is_read_as_utc_not_local(stored, expected_utc):
    """Reading it as local time would offset every duration by the machine's timezone."""
    fallback = datetime(2000, 1, 1, tzinfo=timezone.utc)
    assert parse_stored_utc(stored, fallback) == expected_utc


@pytest.mark.parametrize("bad", [None, "", "not a date"])
def test_an_unreadable_timestamp_falls_back(bad):
    fallback = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert parse_stored_utc(bad, fallback) == fallback


def test_a_broken_table_does_not_raise_into_the_workflow(repo):
    repo.conn.execute("DROP TABLE scraping_sessions")
    repo.conn.commit()

    assert repo.create("followers", "TARGET", "@a") is None
    assert repo.update_count(1, 5) is False
    assert repo.cleanup_orphans() == 0
