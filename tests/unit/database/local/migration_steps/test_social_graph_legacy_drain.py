"""Draining the legacy follow-graph tables must never lose rows, nor stall in silence.

The two legacy tables used to be drained under a single guard, so one side failing
aborted the other and left BOTH in place — on every boot, at debug level, where nobody
would ever read it. Rows that never reached the unified store looked exactly like a
finished migration.
"""

import sqlite3

import pytest

from taktik.core.database.local.migration_steps.social_graph import (
    run_social_graph_sync_migrations,
)


_LEGACY_FOLLOWING = """
    CREATE TABLE following_sync (
        id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, username TEXT NOT NULL,
        display_name TEXT DEFAULT '', first_seen_at TEXT DEFAULT (datetime('now')),
        last_seen_at TEXT DEFAULT (datetime('now')), is_follower_back INTEGER DEFAULT NULL,
        followed_by_bot INTEGER DEFAULT 0, unfollowed_at TEXT DEFAULT NULL, source TEXT DEFAULT 'sync',
        UNIQUE(account_id, username))
"""

_LEGACY_FOLLOWERS = """
    CREATE TABLE followers_sync (
        id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, username TEXT NOT NULL,
        display_name TEXT DEFAULT '', first_seen_at TEXT DEFAULT (datetime('now')),
        last_seen_at TEXT DEFAULT (datetime('now')), is_following_back INTEGER DEFAULT NULL,
        source TEXT DEFAULT 'sync', UNIQUE(account_id, username))
"""


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


def _tables(connection):
    return {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _rows(connection, direction):
    return [
        row["username"]
        for row in connection.execute(
            "SELECT username FROM social_graph_sync WHERE direction = ?", (direction,)
        )
    ]


def test_both_sides_are_drained_and_dropped(conn):
    conn.execute(_LEGACY_FOLLOWING)
    conn.execute(_LEGACY_FOLLOWERS)
    conn.execute("INSERT INTO following_sync (account_id, username) VALUES (1, 'followed')")
    conn.execute("INSERT INTO followers_sync (account_id, username) VALUES (1, 'fan')")

    run_social_graph_sync_migrations(conn.cursor())

    assert _rows(conn, "following") == ["followed"]
    assert _rows(conn, "follower") == ["fan"]
    assert "following_sync" not in _tables(conn)
    assert "followers_sync" not in _tables(conn)


def test_a_broken_side_does_not_strand_the_other(conn):
    """The regression this guards: one bad shape used to abort both sides."""
    # An older `following_sync` missing the columns the backfill selects.
    conn.execute(
        "CREATE TABLE following_sync (account_id INTEGER, username TEXT)"
    )
    conn.execute("INSERT INTO following_sync (account_id, username) VALUES (1, 'stranded')")
    conn.execute(_LEGACY_FOLLOWERS)
    conn.execute("INSERT INTO followers_sync (account_id, username) VALUES (1, 'fan')")

    run_social_graph_sync_migrations(conn.cursor())

    # The healthy side went through and is gone.
    assert _rows(conn, "follower") == ["fan"]
    assert "followers_sync" not in _tables(conn)
    # The broken side is KEPT, rows and all: dropping it would lose them.
    assert "following_sync" in _tables(conn)
    assert conn.execute("SELECT COUNT(*) FROM following_sync").fetchone()[0] == 1


def test_a_failed_drain_is_reported_loudly(conn, caplog):
    """A stranded table at debug level reads exactly like a finished migration."""
    from loguru import logger

    messages = []
    sink_id = logger.add(lambda m: messages.append(m.record), level="WARNING")
    try:
        conn.execute("CREATE TABLE following_sync (account_id INTEGER, username TEXT)")
        run_social_graph_sync_migrations(conn.cursor())
    finally:
        logger.remove(sink_id)

    assert any("following_sync" in record["message"] for record in messages)


def test_running_twice_changes_nothing(conn):
    conn.execute(_LEGACY_FOLLOWING)
    conn.execute("INSERT INTO following_sync (account_id, username) VALUES (1, 'followed')")

    run_social_graph_sync_migrations(conn.cursor())
    run_social_graph_sync_migrations(conn.cursor())

    assert _rows(conn, "following") == ["followed"]


def test_a_database_that_never_had_the_legacy_tables_is_fine(conn):
    """The common case now: nothing to drain, nothing to drop."""
    run_social_graph_sync_migrations(conn.cursor())

    assert "social_graph_sync" in _tables(conn)
    assert _rows(conn, "following") == []
