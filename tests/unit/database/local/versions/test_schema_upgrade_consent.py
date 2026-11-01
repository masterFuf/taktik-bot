"""From source, the engine creates a new base but never raises an existing one without consent.

An installed app refuses a base newer than it knows: code run from its folder that raised the base
on its way would lock that app out. The installer's engine (a PyInstaller build) upgrades as before.
"""

import functools
import hashlib
import os
import sqlite3
import sys
from pathlib import Path

import pytest

from bridges.tools.schema import schema_bridge
from taktik.core.database.local import service as service_module
from taktik.core.database.local.service import LocalDatabaseService
from taktik.core.database.local.versions import opening, runner
from taktik.core.database.local.versions.catalog import (
    ADDITIVE,
    MIGRATIONS,
    VERSIONS_DIR,
    Migration,
    schema_version,
)
from taktik.core.database.local.versions.legacy import run_bot_legacy_steps
from taktik.core.database.local.versions.opening import (
    LEGACY,
    NUMBERED,
    UNDER_APP_ENV,
    UPGRADE_CONSENT_ENV,
    SchemaNotReady,
    SchemaUpgradeNeedsConsent,
    ensure_schema,
)
from taktik.core.database.local.versions.runner import (
    BEHIND,
    NEEDS_UPGRADE_CONSENT,
    inspect_database,
    migrate_database,
    running_from_source,
)
from taktik.core.database.local.versions.sql_text import split_statements

TARGET = schema_version()


def _create_test_table(conn):
    conn.execute("CREATE TABLE test_only_step (id INTEGER PRIMARY KEY)")


# A later version of the schema, for these tests only: the real list stays as it is.
NEXT_VERSION = (*MIGRATIONS, Migration(TARGET + 1, "test_only_step", ADDITIVE, apply_fn=_create_test_table))


@pytest.fixture(autouse=True)
def _from_source_on_its_own(monkeypatch):
    """Code run from its folder, by nobody: the case of the CLI."""
    opening.forget_checks()
    monkeypatch.setattr(runner, "running_from_source", lambda: True)
    monkeypatch.delenv(UNDER_APP_ENV, raising=False)
    monkeypatch.delenv(UPGRADE_CONSENT_ENV, raising=False)
    monkeypatch.delenv("TAKTIK_DB_PATH", raising=False)
    yield
    opening.forget_checks()


@pytest.fixture
def installed_engine(monkeypatch):
    monkeypatch.setattr(runner, "running_from_source", lambda: False)


def recognized_base(path: Path) -> Path:
    """The bot's 1.9.8 schema at version 0, in WAL mode, closed, with one account."""
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("BEGIN")
    for statement in split_statements((VERSIONS_DIR / "m0001_baseline.sql").read_text(encoding="utf-8")):
        conn.execute(statement)
    conn.execute("INSERT INTO accounts (platform, username) VALUES ('instagram', 'compte_test')")
    conn.execute("COMMIT")
    conn.close()
    return path


def base_one_version_behind(path: Path, monkeypatch) -> Path:
    """A base at today's version, while the code expects the next one (the real shape of a new migration)."""
    recognized_base(path)
    monkeypatch.setattr(runner, "running_from_source", lambda: False)
    assert migrate_database(path, backup_dir=path.parent / "first-backups").success
    monkeypatch.setattr(runner, "running_from_source", lambda: True)
    assert inspect_database(path, NEXT_VERSION).state == BEHIND
    return path


def code_expects_next_version(monkeypatch) -> None:
    """`ensure_schema` reads the real list: point it at the longer one."""
    monkeypatch.setattr(opening, "inspect_database", functools.partial(inspect_database, catalog=NEXT_VERSION))
    monkeypatch.setattr(opening, "migrate_database", functools.partial(migrate_database, catalog=NEXT_VERSION))
    monkeypatch.setattr(opening, "schema_version", lambda: TARGET + 1)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def user_version(path: Path) -> int:
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def has_table(path: Path, name: str) -> bool:
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None
    finally:
        conn.close()


def side_files(path: Path) -> list:
    return [suffix for suffix in ("-wal", "-shm", "-journal") if Path(str(path) + suffix).exists()]


def files_in(folder: Path) -> list:
    return sorted(os.listdir(folder))


def assert_nothing_changed(path: Path, sha_before: str, files_before: list) -> None:
    """No byte, no side file, no backup folder: the refusal leaves the folder as it found it."""
    assert sha256(path) == sha_before
    assert files_in(path.parent) == files_before


# ─── the engine knows where it runs ───────────────────────────────────────────

def test_the_pyinstaller_build_is_not_source(monkeypatch):
    monkeypatch.undo()
    assert running_from_source() is True
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert running_from_source() is False


# ─── migrate_database: the one place that raises a base ───────────────────────

def test_from_source_without_consent_a_base_behind_is_refused_untouched(tmp_path, monkeypatch):
    path = base_one_version_behind(tmp_path / "taktik-data.db", monkeypatch)
    sha_before, files_before = sha256(path), files_in(tmp_path)

    result = migrate_database(path, catalog=NEXT_VERSION)

    assert not result.success
    assert result.action == NEEDS_UPGRADE_CONSENT
    assert result.backup is None
    assert_nothing_changed(path, sha_before, files_before)
    assert user_version(path) == TARGET
    assert not has_table(path, "test_only_step")


def test_with_consent_it_goes_up_after_its_backup(tmp_path, monkeypatch):
    path = base_one_version_behind(tmp_path / "taktik-data.db", monkeypatch)

    result = migrate_database(path, catalog=NEXT_VERSION, upgrade_consented=True)

    assert result.success and result.action == "migrated"
    assert user_version(path) == TARGET + 1
    assert has_table(path, "test_only_step")
    assert user_version(Path(result.backup["path"])) == TARGET
    assert not has_table(Path(result.backup["path"]), "test_only_step")


def test_the_installed_engine_goes_up_without_asking_after_its_backup(tmp_path, monkeypatch, installed_engine):
    path = recognized_base(tmp_path / "taktik-data.db")
    monkeypatch.undo()
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    result = migrate_database(path)

    assert result.success and result.action == "stamped"
    assert user_version(path) == TARGET
    assert Path(result.backup["path"]).exists()


@pytest.mark.parametrize("empty_file", [False, True])
def test_a_new_base_is_created_without_consent(tmp_path, empty_file):
    path = tmp_path / "taktik-data.db"
    if empty_file:
        path.write_bytes(b"")

    result = migrate_database(path)

    assert result.success and result.action == "created"
    assert user_version(path) == TARGET
    assert not (tmp_path / "backups").exists()


def test_a_base_at_the_version_opens_without_consent(tmp_path, monkeypatch):
    path = recognized_base(tmp_path / "taktik-data.db")
    monkeypatch.setattr(runner, "running_from_source", lambda: False)
    assert migrate_database(path).success
    monkeypatch.setattr(runner, "running_from_source", lambda: True)
    sha_before = sha256(path)

    result = migrate_database(path)

    assert result.success and result.action == "none"
    assert sha256(path) == sha_before


def test_a_refused_unrecognized_base_makes_no_backup_either(tmp_path):
    """Before the guard, this state wrote a backup and asked for the 1.9.8 app."""
    path = tmp_path / "taktik-data.db"
    run_bot_legacy_steps(path)
    sha_before, files_before = sha256(path), files_in(tmp_path)

    result = migrate_database(path)

    assert result.action == NEEDS_UPGRADE_CONSENT
    assert_nothing_changed(path, sha_before, files_before)


# ─── ensure_schema: every opening of the bot on its own ───────────────────────

def test_an_opening_refuses_a_base_behind_and_leaves_nothing_behind(tmp_path, monkeypatch):
    path = base_one_version_behind(tmp_path / "taktik-data.db", monkeypatch)
    code_expects_next_version(monkeypatch)
    sha_before, files_before = sha256(path), files_in(tmp_path)

    with pytest.raises(SchemaUpgradeNeedsConsent) as refusal:
        ensure_schema(path)

    assert (refusal.value.user_version, refusal.value.target_version) == (TARGET, TARGET + 1)
    assert UPGRADE_CONSENT_ENV in str(refusal.value)
    assert_nothing_changed(path, sha_before, files_before)
    assert user_version(path) == TARGET


def test_an_opening_goes_up_with_the_consent_for_this_version(tmp_path, monkeypatch):
    path = base_one_version_behind(tmp_path / "taktik-data.db", monkeypatch)
    code_expects_next_version(monkeypatch)

    assert ensure_schema(path, env={UPGRADE_CONSENT_ENV: str(TARGET + 1)}) == NUMBERED

    assert user_version(path) == TARGET + 1
    assert list((tmp_path / "backups").glob(f"taktik-data.v{TARGET}-v{TARGET + 1}.*.db"))


@pytest.mark.parametrize("value", ["1000", "yes", "", " "])
def test_a_consent_for_another_version_is_no_consent(tmp_path, monkeypatch, value):
    """A variable left in a shell must not raise the base at the next migration."""
    path = base_one_version_behind(tmp_path / "taktik-data.db", monkeypatch)
    code_expects_next_version(monkeypatch)
    sha_before, files_before = sha256(path), files_in(tmp_path)

    with pytest.raises(SchemaUpgradeNeedsConsent):
        ensure_schema(path, env={UPGRADE_CONSENT_ENV: value})

    assert_nothing_changed(path, sha_before, files_before)


def test_the_service_refuses_a_recognized_base_at_version_0(tmp_path):
    path = recognized_base(tmp_path / "taktik-data.db")
    sha_before, files_before = sha256(path), files_in(tmp_path)

    with pytest.raises(SchemaUpgradeNeedsConsent):
        LocalDatabaseService(str(path))

    assert_nothing_changed(path, sha_before, files_before)
    assert user_version(path) == 0


def test_the_old_steps_do_not_run_on_a_refused_base(tmp_path, monkeypatch):
    """A version-0 base the list does not know goes to the old un-numbered steps, which write."""
    def forbidden(*_args, **_kwargs):
        raise AssertionError("the old steps ran on a base nobody agreed to raise")

    path = tmp_path / "taktik-data.db"
    run_bot_legacy_steps(path)
    sha_before, files_before = sha256(path), files_in(tmp_path)
    monkeypatch.setattr(service_module, "create_schema", forbidden)
    monkeypatch.setattr(service_module, "run_migrations", forbidden)

    with pytest.raises(SchemaUpgradeNeedsConsent):
        LocalDatabaseService(str(path))

    assert_nothing_changed(path, sha_before, files_before)


def test_the_old_steps_run_with_consent_and_the_stamp_follows_them(tmp_path, monkeypatch):
    path = recognized_base(tmp_path / "taktik-data.db")
    monkeypatch.setenv(UPGRADE_CONSENT_ENV, str(TARGET))

    db = LocalDatabaseService(str(path))
    db.close()

    assert user_version(path) == TARGET


def test_the_stamp_after_the_old_steps_keeps_the_consent(tmp_path, monkeypatch):
    """`stamp_if_recognized` raises the base too: it must read the same consent."""
    path = recognized_base(tmp_path / "taktik-data.db")

    assert opening.stamp_if_recognized(path, env={}) == LEGACY
    assert user_version(path) == 0
    assert opening.stamp_if_recognized(path, env={UPGRADE_CONSENT_ENV: str(TARGET)}) == NUMBERED
    assert user_version(path) == TARGET


def test_the_installed_engine_opens_as_before(tmp_path, monkeypatch, installed_engine):
    path = recognized_base(tmp_path / "taktik-data.db")

    assert ensure_schema(path) == NUMBERED
    assert user_version(path) == TARGET


def test_a_new_base_and_a_base_at_the_version_open_from_source(tmp_path):
    path = tmp_path / "taktik-data.db"

    assert ensure_schema(path) == NUMBERED
    assert user_version(path) == TARGET
    opening.forget_checks()
    assert ensure_schema(path) == NUMBERED


def test_under_the_app_the_consent_of_a_shell_changes_nothing(tmp_path, monkeypatch):
    """Under the app, only its gate raises the base; a bridge refuses as before."""
    path = recognized_base(tmp_path / "taktik-data.db")
    sha_before = sha256(path)
    monkeypatch.setenv(UNDER_APP_ENV, "4242")
    monkeypatch.setenv(UPGRADE_CONSENT_ENV, str(TARGET))

    with pytest.raises(SchemaNotReady, match="restart the desktop app"):
        ensure_schema(path)

    assert sha256(path) == sha_before


def test_a_refused_opening_is_not_remembered_as_checked(tmp_path, monkeypatch):
    path = recognized_base(tmp_path / "taktik-data.db")
    with pytest.raises(SchemaUpgradeNeedsConsent):
        ensure_schema(path)

    assert ensure_schema(path, env={UPGRADE_CONSENT_ENV: str(TARGET)}) == NUMBERED


# ─── schema_bridge: the way the app raises it ─────────────────────────────────

class _Ipc:
    def __init__(self):
        self.events = []

    def send(self, msg_type, **kwargs):
        self.events.append({"type": msg_type, **kwargs})

    def error(self, error, error_code=None, **extra):
        self.events.append({"type": "error", "error": error, "error_code": error_code})


def test_the_bridge_asks_for_consent_and_writes_nothing(tmp_path):
    path = recognized_base(tmp_path / "taktik-data.db")
    sha_before, files_before = sha256(path), files_in(tmp_path)
    ipc = _Ipc()

    code = schema_bridge.run({"command": "migrate", "db": str(path)}, ipc=ipc)

    assert code == schema_bridge.EXIT_NEEDS_UPGRADE_CONSENT
    results = [event for event in ipc.events if event["type"] == "schema_result"]
    assert results[0]["action"] == NEEDS_UPGRADE_CONSENT
    assert not [event for event in ipc.events if event["type"] == "error"]
    assert_nothing_changed(path, sha_before, files_before)


def test_the_bridge_goes_up_with_the_consent_of_its_config(tmp_path):
    path = recognized_base(tmp_path / "taktik-data.db")

    code = schema_bridge.run({"command": "migrate", "db": str(path), "upgradeConsent": True}, ipc=_Ipc())

    assert code == schema_bridge.EXIT_OK
    assert user_version(path) == TARGET
    assert list((tmp_path / "backups").glob("taktik-data.v0-v*.db"))


def test_the_bridge_does_not_read_the_consent_of_the_shell(tmp_path, monkeypatch):
    path = recognized_base(tmp_path / "taktik-data.db")
    sha_before = sha256(path)
    monkeypatch.setenv(UPGRADE_CONSENT_ENV, str(TARGET))

    code = schema_bridge.run({"command": "migrate", "db": str(path)}, ipc=_Ipc())

    assert code == schema_bridge.EXIT_NEEDS_UPGRADE_CONSENT
    assert sha256(path) == sha_before


def test_the_bridge_of_the_installed_engine_goes_up_without_consent(tmp_path, installed_engine):
    path = recognized_base(tmp_path / "taktik-data.db")

    assert schema_bridge.run({"command": "migrate", "db": str(path)}, ipc=_Ipc()) == schema_bridge.EXIT_OK
    assert user_version(path) == TARGET
