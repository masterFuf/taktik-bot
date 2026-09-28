"""L4: every opening of the local database goes through the numbered schema check."""

import hashlib
import sqlite3
from pathlib import Path

import pytest

from taktik.core.database.local import service as service_module
from taktik.core.database.local.service import LocalDatabaseService
from taktik.core.database.local.versions import opening
from taktik.core.database.local.versions.catalog import VERSIONS_DIR, schema_version
from taktik.core.database.local.versions.opening import (
    LEGACY,
    NUMBERED,
    UNDER_APP_ENV,
    SchemaNotReady,
    ensure_schema,
    open_connection,
)
from taktik.core.database.local.versions.runner import CURRENT, inspect_database, migrate_database
from taktik.core.database.local.versions.sql_text import split_statements
from taktik.core.database.local.versions.upkeep import run_data_upkeep

TARGET = schema_version()


@pytest.fixture(autouse=True)
def _fresh_checks(monkeypatch):
    opening.forget_checks()
    monkeypatch.delenv(UNDER_APP_ENV, raising=False)
    yield
    opening.forget_checks()


def legacy_base(path: Path) -> Path:
    """The bot's 1.9.8 objects plus an app table and an app trigger on a bot table, version 0."""
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("BEGIN")
    for statement in split_statements((VERSIONS_DIR / "m0001_baseline.sql").read_text(encoding="utf-8")):
        conn.execute(statement)
    conn.execute("CREATE TABLE app_config (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("CREATE TRIGGER trg_accounts_touch AFTER UPDATE OF username ON accounts BEGIN "
                 "UPDATE accounts SET updated_at = datetime('now') WHERE id = NEW.id; END")
    conn.execute("INSERT INTO accounts (platform, username) VALUES ('instagram', 'compte_test')")
    conn.execute("COMMIT")
    conn.close()
    return path


def current_base(path: Path) -> Path:
    legacy_base(path)
    assert migrate_database(path, backup_dir=path.parent / "backups").success
    return path


def schema_rows(path: Path):
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name").fetchall()
    finally:
        conn.close()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar(path: Path, sql: str):
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def no_old_steps(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("the old un-numbered schema steps ran on a numbered base")

    monkeypatch.setattr(service_module, "create_schema", forbidden)
    monkeypatch.setattr(service_module, "run_migrations", forbidden)


# ─── on its own (CLI) ─────────────────────────────────────────────────────────

def test_a_new_base_on_its_own_keeps_the_old_steps(tmp_path):
    path = tmp_path / "taktik-data.db"
    db = LocalDatabaseService(str(path))
    db.close()
    assert scalar(path, "PRAGMA user_version") == 0
    assert scalar(path, "SELECT COUNT(*) FROM sqlite_master WHERE name = 'accounts'") == 1
    assert ensure_schema(path) == LEGACY


def test_a_recognized_base_is_stamped_at_its_first_opening_on_its_own(tmp_path, monkeypatch):
    path = legacy_base(tmp_path / "taktik-data.db")
    before = schema_rows(path)
    no_old_steps(monkeypatch)
    db = LocalDatabaseService(str(path))
    db.close()
    assert scalar(path, "PRAGMA user_version") == TARGET
    after = schema_rows(path)
    assert [r for r in after if r[1] != "schema_migrations"] == before
    assert list((tmp_path / "backups").glob("taktik-data.v0-v1.*.db"))


def test_a_numbered_base_gets_no_schema_step_only_the_data_upkeep(tmp_path, monkeypatch):
    path = current_base(tmp_path / "taktik-data.db")
    before = schema_rows(path)
    conn = sqlite3.connect(str(path))
    conn.execute("DELETE FROM device_identity")
    conn.execute("INSERT INTO sessions_unified (platform, sync_id) VALUES ('instagram', NULL)")
    conn.commit()
    conn.close()
    no_old_steps(monkeypatch)
    db = LocalDatabaseService(str(path))
    db.close()
    assert schema_rows(path) == before
    assert scalar(path, "SELECT COUNT(*) FROM device_identity") == 1
    assert scalar(path, "SELECT COUNT(*) FROM sessions_unified WHERE sync_id IS NULL") == 0


def test_data_upkeep_writes_what_the_old_steps_wrote(tmp_path):
    """Same data effect as the old steps on the same base: kept as is (decision of 2026-09-25)."""
    def seeded(name):
        (tmp_path / name).mkdir()
        path = current_base(tmp_path / name / "taktik-data.db")
        conn = sqlite3.connect(str(path))
        conn.execute("DELETE FROM device_identity")
        conn.execute("INSERT INTO sessions_unified (platform, sync_id) VALUES ('instagram', NULL)")
        conn.execute("INSERT INTO interactions (platform, interaction_type, sync_id) VALUES ('instagram', 'like', NULL)")
        conn.execute(
            "INSERT INTO scraping_sessions (scraping_id, scraping_type, source_type, source_name, sync_id) "
            "VALUES (7, 'followers', 'account', 'cible', 'a')")
        conn.commit()
        conn.close()
        return path

    def facts(path):
        conn = sqlite3.connect(str(path))
        try:
            return (
                conn.execute("SELECT COUNT(*) FROM device_identity").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM sessions_unified WHERE sync_id IS NULL").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM interactions WHERE sync_id IS NULL").fetchone()[0],
                conn.execute("SELECT sync_id FROM scraping_sessions WHERE scraping_id = 7").fetchall(),
            )
        finally:
            conn.close()

    old = seeded("old")
    from taktik.core.database.local.versions.legacy import run_bot_legacy_steps

    run_bot_legacy_steps(old)
    new = seeded("new")
    conn = sqlite3.connect(str(new))
    run_data_upkeep(conn)
    conn.close()
    assert facts(new) == facts(old) == (1, 0, 0, [("a",)])


# ─── under the desktop app ────────────────────────────────────────────────────

def test_under_the_app_a_base_not_at_the_version_is_refused_untouched(tmp_path, monkeypatch):
    path = legacy_base(tmp_path / "taktik-data.db")
    before = sha256(path)
    monkeypatch.setenv(UNDER_APP_ENV, "4242")
    with pytest.raises(SchemaNotReady, match="restart the desktop app"):
        LocalDatabaseService(str(path))
    assert sha256(path) == before
    assert not (tmp_path / "backups").exists()


def test_under_the_app_a_numbered_base_opens_without_schema_step(tmp_path, monkeypatch):
    path = current_base(tmp_path / "taktik-data.db")
    before = schema_rows(path)
    monkeypatch.setenv(UNDER_APP_ENV, "4242")
    no_old_steps(monkeypatch)
    db = LocalDatabaseService(str(path))
    db.close()
    assert schema_rows(path) == before


def test_under_the_app_even_a_missing_base_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(UNDER_APP_ENV, "4242")
    with pytest.raises(SchemaNotReady):
        ensure_schema(tmp_path / "taktik-data.db")
    assert not (tmp_path / "taktik-data.db").exists()


@pytest.mark.parametrize("under_app", [False, True])
def test_a_base_newer_than_the_bot_is_refused_untouched(tmp_path, monkeypatch, under_app):
    path = current_base(tmp_path / "taktik-data.db")
    conn = sqlite3.connect(str(path))
    conn.execute(f"PRAGMA user_version = {TARGET + 1}")
    conn.close()
    before = sha256(path)
    if under_app:
        monkeypatch.setenv(UNDER_APP_ENV, "4242")
    with pytest.raises(SchemaNotReady, match="newer than this bot"):
        LocalDatabaseService(str(path))
    assert sha256(path) == before


# ─── the direct openings ──────────────────────────────────────────────────────

def test_the_direct_openings_go_through_the_check(tmp_path, monkeypatch):
    from taktik.core.database.messaging import DmConversationService, SentDMService
    from taktik.core.database.notifications import NotificationService
    from taktik.core.database.repositories import get_repository
    from taktik.core.database.repositories.messaging import SentDMRepository

    path = legacy_base(tmp_path / "taktik-data.db")
    monkeypatch.setenv("TAKTIK_DB_PATH", str(path))
    monkeypatch.setenv(UNDER_APP_ENV, "4242")
    openers = [
        lambda: get_repository(SentDMRepository, str(path)),
        NotificationService._open,
        SentDMService._open_repository,
        DmConversationService._open,
    ]
    for opener in openers:
        opening.forget_checks()
        with pytest.raises(SchemaNotReady):
            opener()

    monkeypatch.delenv(UNDER_APP_ENV)
    opening.forget_checks()
    migrate_database(path, backup_dir=tmp_path / "backups")
    monkeypatch.setenv(UNDER_APP_ENV, "4242")
    for opener in openers:
        opening.forget_checks()
        opened = opener()
        conn = opened[1] if isinstance(opened, tuple) else getattr(opened, "_conn", opened)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == TARGET
        conn.close()


def test_the_welcome_dm_probe_opening_goes_through_the_check(tmp_path, monkeypatch):
    from taktik.core.database.messaging import open_existing_database

    path = legacy_base(tmp_path / "taktik-data.db")
    monkeypatch.setenv("TAKTIK_DB_PATH", str(path))
    monkeypatch.setenv(UNDER_APP_ENV, "4242")
    with pytest.raises(SchemaNotReady):
        open_existing_database()


def test_the_check_runs_once_per_process_and_base(tmp_path, monkeypatch):
    path = current_base(tmp_path / "taktik-data.db")
    calls = []
    real = opening.inspect_database

    def counting(*args, **kwargs):
        calls.append(args[0])
        return real(*args, **kwargs)

    monkeypatch.setattr(opening, "inspect_database", counting)
    for _ in range(3):
        open_connection(path).close()
    assert len(calls) == 1
    assert inspect_database(path).state == CURRENT
