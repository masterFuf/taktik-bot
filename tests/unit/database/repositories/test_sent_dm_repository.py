"""Unit tests for sent DM duplicate-prevention repository."""

import re
import sqlite3

import pytest

from taktik.core.database.local.versions.runner import migrate_database
from taktik.core.database.repositories.messaging import SentDMRepository


def test_recorded_dm_is_detected_per_platform(conn):
    repo = SentDMRepository(conn)

    assert repo.check_already_sent(1, "TargetUser", platform="instagram") is False

    repo.record(
        account_id=1,
        recipient="TargetUser",
        message="hello",
        success=True,
        platform="instagram",
    )

    assert repo.check_already_sent(1, "targetuser", platform="instagram") is True
    assert repo.check_already_sent(1, "targetuser", platform="tiktok") is False


def test_record_updates_existing_dm_marker(conn):
    repo = SentDMRepository(conn)

    repo.record(1, "targetuser", "first", True, platform="instagram")
    repo.record(1, "targetuser", "second", False, error_message="blocked", platform="instagram")

    rows = repo.query("SELECT * FROM sent_dms")

    assert len(rows) == 1
    assert rows[0]["success"] == 0
    assert rows[0]["error_message"] == "blocked"

# The sync key, on the schema of an operator's base (the numbered list: sent_dms has its sync_id).
# Turso pushes only the rows that carry one: a marker written without it never left the PC.


@pytest.fixture
def numbered_conn(tmp_path):
    path = tmp_path / "taktik-data.db"
    assert migrate_database(path, backup_dir=tmp_path / "backups").success
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    yield con
    con.close()


def _keys(conn):
    return [row["sync_id"] for row in conn.execute("SELECT sync_id FROM sent_dms ORDER BY id")]


def test_a_recorded_dm_carries_its_sync_key(numbered_conn):
    repo = SentDMRepository(numbered_conn)

    repo.record(1, "TargetUser", "hello", True, platform="instagram")
    repo.record(1, "other", "hello", True, platform="tiktok")

    keys = _keys(numbered_conn)
    assert len(keys) == 2
    assert all(isinstance(key, str) and re.fullmatch(r"[0-9a-f]{32}", key) for key in keys), keys
    assert keys[0] != keys[1]


def test_a_marker_recorded_again_keeps_a_key(numbered_conn):
    repo = SentDMRepository(numbered_conn)

    repo.record(1, "targetuser", "first", False, error_message="blocked", platform="instagram")
    repo.record(1, "targetuser", "second", True, platform="instagram")

    rows = numbered_conn.execute("SELECT success, sync_id FROM sent_dms").fetchall()
    assert len(rows) == 1
    assert rows[0]["success"] == 1
    assert re.fullmatch(r"[0-9a-f]{32}", rows[0]["sync_id"] or "")


def test_a_base_without_the_sync_column_still_records(conn):
    """The bot's old steps alone (a base the desktop never opened) have no sync column: nothing
    syncs from such a base, and the marker is recorded without a key rather than lost."""
    repo = SentDMRepository(conn)

    repo.record(1, "TargetUser", "hello", True, platform="instagram")

    assert "sync_id" not in {row[1] for row in conn.execute("PRAGMA table_info(sent_dms)")}
    assert repo.check_already_sent(1, "targetuser", platform="instagram") is True

