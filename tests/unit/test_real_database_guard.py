"""The suite can never open the operator's database.

Without `TAKTIK_DB_PATH` the bot resolves `%APPDATA%/taktik-desktop/taktik-data.db`, the base
the desktop app works on. A test that reached a default accessor opened it: the TikTok reader of
`ProfileQualification` called the singleton past the `_db()` seam its test stubbed, and each run
rebuilt the WAL index of the operator's base (its -shm changed date, its content did not).

`tests/unit/conftest.py` moves the default folder to a throwaway directory before `taktik` is
imported and refuses, through an audit hook, any SQLite open there and any open of the
operator's folders. A refusal fails the test even when the code under test swallows it. These
tests trigger refusals on purpose, only on throwaway paths, and `take()` them.
"""

import os
import sqlite3

import pytest

from taktik.core.database.local.paths import get_default_database_path
from taktik.core.database.local.service import get_local_database
from taktik.core.database.profile_qualification import ProfileQualification


def _norm(path):
    return os.path.normcase(os.path.abspath(str(path)))


def test_the_default_base_is_a_throwaway_one():
    assert "TAKTIK_DB_PATH" not in os.environ
    assert "TAKTIK_DATA_DIR" not in os.environ
    assert os.path.basename(os.environ["APPDATA"]).startswith("taktik-tests-appdata-")
    assert _norm(get_default_database_path()).startswith(_norm(os.environ["APPDATA"]))


def test_the_default_base_is_refused_before_sqlite_touches_it(real_database_guard):
    """The default base is an empty decoy, so code gated on its existence gets caught too."""
    default = get_default_database_path()
    for target in (default, f"file:{default}?mode=ro"):
        with pytest.raises(PermissionError):
            sqlite3.connect(target, uri=target.startswith("file:"))
    assert os.path.getsize(default) == 0
    assert not os.path.exists(default + "-wal") and not os.path.exists(default + "-shm")
    assert [path for _, path, _ in real_database_guard.take()] == [_norm(default)] * 2


def test_the_singleton_cannot_reach_the_default_base(real_database_guard):
    with pytest.raises(PermissionError):
        get_local_database()
    assert real_database_guard.take()


def test_a_refusal_the_code_swallows_is_still_recorded(real_database_guard):
    """`load_many` never raises: the hit, not the exception, is what fails such a test."""
    assert ProfileQualification.load("somebody", platform="tiktok") is None
    assert real_database_guard.take()


def test_a_base_in_tmp_path_is_allowed(tmp_path, real_database_guard):
    connection = sqlite3.connect(tmp_path / "throwaway.db")
    connection.execute("CREATE TABLE t (x)")
    connection.close()
    assert real_database_guard.take() == []


def test_the_rules(tmp_path, real_database_guard):
    guard = type(real_database_guard)(
        sealed_folders=[tmp_path / "operator"],
        sealed_files=[tmp_path / "elsewhere" / "taktik-data.db"],
        default_folder=tmp_path / "default",
    )
    refused = guard._refused
    assert refused("open", _norm(tmp_path / "operator" / "taktik-data.db-shm"))
    assert refused("open", _norm(tmp_path / "operator" / "logs" / "taktik.log"))
    assert refused("open", _norm(tmp_path / "elsewhere" / "taktik-data.db-wal"))
    assert refused("sqlite3.connect", _norm(tmp_path / "default" / "taktik-data.db"))
    assert not refused("open", _norm(tmp_path / "default" / "logs" / "taktik.log"))
    assert not refused("sqlite3.connect", _norm(tmp_path / "elsewhere" / "other.db"))
    assert not refused("sqlite3.connect", _norm(tmp_path / "operator-copy" / "taktik-data.db"))

    with pytest.raises(PermissionError):
        guard("sqlite3.connect", (str(tmp_path / "operator" / "taktik-data.db"),))
    assert guard("sqlite3.connect", (":memory:",)) is None
    assert [event for event, _, _ in guard.take()] == ["sqlite3.connect"]
