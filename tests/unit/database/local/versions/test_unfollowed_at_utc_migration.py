"""Migration 2: the `unfollowed_at` dates written in the machine's local time move to UTC, once.

Until the writer moved to SQLite's `datetime('now')`, `social_graph_sync.unfollowed_at` was
Python's `datetime.now()`: the local time of the machine, two hours ahead of the other dates of the
follow graph in a French summer. The table is never synced, so the machine that migrates a base is
the one that wrote its rows, and SQLite converts with that machine's offset.

The migration runs in a child process whose machine lives three hours east of UTC (`TZ=TKT-3`, read
by SQLite when the process starts, on Windows as on Linux): the conversion shows on any machine, a
UTC one included. SQLite takes the offset of each row's own date, so a zone with summer time would
convert September rows by its summer offset; a fixed zone keeps the expected values plain.
"""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from taktik.core.database.local.versions.catalog import DATA, MIGRATIONS, VERSIONS_DIR
from taktik.core.database.local.versions.journal import read_journal
from taktik.core.database.local.versions.runner import migrate_database
from taktik.core.database.local.versions.sql_text import split_statements
from unit.paths import CORE

EAST_OF_UTC = "TKT-3"
UNFOLLOWED_AT_UTC = next(m for m in MIGRATIONS if m.name == "unfollowed_at_utc")
BEFORE = MIGRATIONS[:UNFOLLOWED_AT_UTC.version - 1]

# (platform, direction, username, unfollowed_at as written, last_seen_at, unfollowed_at expected after)
ROWS = (
    # Written in local time by the old writer: three hours earlier in UTC.
    ("instagram", "following", "closed_by_unfollow", "2026-09-24 23:30:00", "2026-09-20 21:00:00",
     "2026-09-24 20:30:00"),
    ("tiktok", "following", "closed_on_tiktok", "2026-09-25 22:05:12", "2026-09-25 19:05:12",
     "2026-09-25 19:05:12"),
    ("instagram", "follower", "follower_gone", "2026-10-03 01:15:00", "2026-10-02 22:15:00",
     "2026-10-02 22:15:00"),
    # Still followed: no date, nothing to convert.
    ("instagram", "following", "still_followed", None, "2026-09-24 21:00:00", None),
    # Copied from the former following_sync, whose unfollow date was SQLite's, in UTC already.
    ("instagram", "following", "from_following_sync", "2026-05-12 06:00:00", "2026-05-01 06:00:00",
     "2026-05-12 06:00:00"),
    # Stamped by the corrected writer, in the same statement as last_seen_at: UTC already.
    ("instagram", "following", "stamped_by_sqlite", "2026-10-19 21:40:00", "2026-10-19 21:40:00",
     "2026-10-19 21:40:00"),
    # Not a date: datetime() would give NULL, and a NULL would reopen the row.
    ("instagram", "following", "not_a_date", "unreadable", "2026-09-24 21:00:00", "unreadable"),
)


def _seed(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executemany(
            "INSERT INTO social_graph_sync (platform, account_id, username, direction, unfollowed_at, last_seen_at) "
            "VALUES (?, 7, ?, ?, ?, ?)",
            [(platform, username, direction, written, last_seen)
             for platform, direction, username, written, last_seen, _ in ROWS],
        )
        conn.commit()
    finally:
        conn.close()


def _base_before_the_migration(path: Path) -> Path:
    """A base as the builds before migration 2 left it, with rows of every kind."""
    result = migrate_database(path, backup_dir=path.parent / "backups", catalog=BEFORE)
    assert result.success and result.action == "created", result.message
    _seed(path)
    return path


def _legacy_1_9_8_base(path: Path) -> Path:
    """A base the 1.9.8 app and bot left behind: the bot's objects, version 0, no journal."""
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("BEGIN")
    for statement in split_statements((VERSIONS_DIR / "m0001_baseline.sql").read_text(encoding="utf-8")):
        conn.execute(statement)
    conn.execute("COMMIT")
    conn.close()
    _seed(path)
    return path


def _migrate_east_of_utc(path: Path) -> dict:
    """`migrate_database` in a process that starts three hours east of UTC."""
    script = (
        "import json, sys\n"
        "from taktik.core.database.local.versions.runner import migrate_database\n"
        "result = migrate_database(sys.argv[1], backup_dir=sys.argv[2], applied_by='test')\n"
        "print(json.dumps({'action': result.action, 'applied': result.applied, 'message': result.message}))\n"
    )
    env = {**os.environ, "PYTHONPATH": str(CORE), "TZ": EAST_OF_UTC}
    proc = subprocess.run([sys.executable, "-c", script, str(path), str(path.parent / "backups")],
                          cwd=str(CORE), env=env, capture_output=True, timeout=120)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")[-2000:]
    return json.loads(proc.stdout.decode("utf-8").strip().splitlines()[-1])


def _unfollowed_at(path: Path) -> dict:
    conn = sqlite3.connect(str(path))
    try:
        return {(platform, direction, username): value for platform, direction, username, value in conn.execute(
            "SELECT platform, direction, username, unfollowed_at FROM social_graph_sync")}
    finally:
        conn.close()


def _expected() -> dict:
    return {(platform, direction, username): after for platform, direction, username, _, _, after in ROWS}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_it_is_a_data_step():
    assert UNFOLLOWED_AT_UTC.kind == DATA


def test_local_dates_move_to_utc_and_the_others_stay(tmp_path):
    path = _base_before_the_migration(tmp_path / "taktik-data.db")

    result = _migrate_east_of_utc(path)

    assert result["action"] == "migrated", result["message"]
    assert result["applied"] == [UNFOLLOWED_AT_UTC.version]
    assert _unfollowed_at(path) == _expected()


def test_a_second_run_changes_nothing(tmp_path):
    """The step is numbered: once the base is at its version, the runner never plays it again."""
    path = _base_before_the_migration(tmp_path / "taktik-data.db")
    _migrate_east_of_utc(path)
    before = _sha256(path)

    again = _migrate_east_of_utc(path)

    assert again["action"] == "none" and again["applied"] == []
    assert _sha256(path) == before
    assert _unfollowed_at(path) == _expected()
    conn = sqlite3.connect(str(path))
    try:
        journal = [(row["version"], row["mode"]) for row in read_journal(conn)]
    finally:
        conn.close()
    assert journal.count((UNFOLLOWED_AT_UTC.version, "applied")) == 1


def test_a_1_9_8_base_is_stamped_then_converted(tmp_path):
    """A base that never had a version: migration 1 is only stamped, migration 2 runs on its rows."""
    path = _legacy_1_9_8_base(tmp_path / "taktik-data.db")

    result = _migrate_east_of_utc(path)

    assert result["action"] == "stamped", result["message"]
    assert UNFOLLOWED_AT_UTC.version in result["applied"]
    assert _unfollowed_at(path) == _expected()
