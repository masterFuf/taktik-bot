"""Numbered schema migrations: catalog, baseline, inspection, migration, backup."""

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from taktik.core.database.local.versions import backup as backup_module
from taktik.core.database.local.versions.backup import AUTO_BACKUP_PATTERN, prune_auto_backups
from taktik.core.database.local.versions.catalog import (
    ADDITIVE,
    BASELINE,
    MIGRATIONS,
    REBUILD,
    VERSIONS_DIR,
    Migration,
    schema_version,
    validate_catalog,
)
from taktik.core.database.local.versions.fingerprint import compare, fingerprint
from taktik.core.database.local.versions.journal import JOURNAL_TABLE, read_journal
from taktik.core.database.local.versions.manifest import build_manifest, load_manifest
from taktik.core.database.local.versions.runner import (
    ABSENT,
    CURRENT,
    LEGACY_RECOGNIZED,
    LEGACY_UNRECOGNIZED,
    TOO_NEW,
    baseline_fingerprint,
    inspect_database,
    migrate_database,
    target_fingerprint,
)
from taktik.core.database.local.versions.sql_text import split_statements, strip_comments

CORE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_ROOT / "scripts"))

import build_schema_baseline  # noqa: E402

TARGET = schema_version()
BASELINE_TEXT = (VERSIONS_DIR / "m0001_baseline.sql").read_text(encoding="utf-8")


# ─── helpers ──────────────────────────────────────────────────────────────────

# A sample of what the desktop app keeps next to the bot's objects: its own tables, a view over
# one of them, and a trigger on a table of the bot. The bot must neither look at them nor touch them.
APP_OBJECTS = (
    "CREATE TABLE app_config (key TEXT PRIMARY KEY, value TEXT)",
    "CREATE TABLE account_device_history (id INTEGER PRIMARY KEY, account_id INTEGER, device_id TEXT)",
    "CREATE INDEX idx_account_device_history_account ON account_device_history(account_id)",
    "CREATE VIEW gmail_accounts AS SELECT a.id, h.device_id FROM accounts a "
    "LEFT JOIN account_device_history h ON h.account_id = a.id",
    "CREATE TRIGGER trg_accounts_touch AFTER UPDATE OF username ON accounts BEGIN "
    "UPDATE accounts SET updated_at = datetime('now') WHERE id = NEW.id; END",
    "INSERT INTO app_config (key, value) VALUES ('onboarding', 'done')",
)


def legacy_base(path: Path, *, extra_sql=(), seed=True, app_objects=True) -> Path:
    """A base shaped like the 1.9.8 app + bot left it: the bot's baseline, a sample of the app's
    objects, version 0, no journal."""
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("BEGIN")
    for statement in split_statements(BASELINE_TEXT):
        conn.execute(statement)
    for statement in (APP_OBJECTS if app_objects else ()):
        conn.execute(statement)
    for statement in extra_sql:
        conn.execute(statement)
    if seed:
        conn.execute("INSERT INTO accounts (platform, username) VALUES ('instagram', 'compte_test')")
        conn.execute("INSERT INTO accounts (platform, username) VALUES ('tiktok', 'compte_test_tt')")
        conn.execute("INSERT INTO device_identity (id, device_id) VALUES (1, 'abc')")
    conn.execute("COMMIT")
    conn.close()
    return path


def app_part(path: Path):
    """Schema rows of the app's sample objects, and the rows of its table."""
    conn = sqlite3.connect(str(path))
    try:
        names = ("app_config", "account_device_history", "idx_account_device_history_account",
                 "gmail_accounts", "trg_accounts_touch")
        rows = conn.execute(
            f"SELECT type, name, tbl_name, sql FROM sqlite_master WHERE name IN ({','.join('?' * len(names))}) "
            "ORDER BY name", names).fetchall()
        return rows, conn.execute("SELECT * FROM app_config").fetchall()
    finally:
        conn.close()


def objects(path: Path):
    conn = sqlite3.connect(str(path))
    try:
        return {
            (typ, name): sql
            for typ, name, sql in conn.execute("SELECT type, name, sql FROM sqlite_master")
        }
    finally:
        conn.close()


def scalar(path: Path, sql: str):
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def side_files(path: Path):
    return sorted(p.name for p in path.parent.iterdir() if p.name.startswith(path.name + "-"))


FIXED_CLOCK = lambda: datetime(2026, 9, 25, tzinfo=timezone.utc)  # noqa: E731


# ─── catalog, baseline file, manifest ─────────────────────────────────────────

def test_catalog_runs_from_one_without_gaps():
    validate_catalog(MIGRATIONS)
    assert MIGRATIONS[0].kind == BASELINE
    assert TARGET == MIGRATIONS[-1].version
    with pytest.raises(ValueError):
        validate_catalog([Migration(1, "baseline", BASELINE, "m0001_baseline.sql"), Migration(3, "x", ADDITIVE)])
    with pytest.raises(ValueError):
        validate_catalog([Migration(1, "x", ADDITIVE, apply_fn=lambda c: None)])


def test_manifest_matches_the_catalog():
    assert load_manifest() == build_manifest()
    assert load_manifest()["schema_version"] == TARGET


def test_baseline_fingerprint_file_matches_migration_one():
    stored = json.loads((VERSIONS_DIR / "baseline_fingerprint.json").read_text(encoding="utf-8"))
    assert stored == baseline_fingerprint()


def test_checksum_ignores_line_endings(tmp_path, monkeypatch):
    lf = MIGRATIONS[0].checksum()
    crlf_dir = tmp_path / "crlf"
    crlf_dir.mkdir()
    (crlf_dir / "m0001_baseline.sql").write_bytes(BASELINE_TEXT.replace("\n", "\r\n").encode("utf-8"))
    retired = (VERSIONS_DIR / "m0001_retired_tables.json").read_text(encoding="utf-8")
    (crlf_dir / "m0001_retired_tables.json").write_bytes(retired.replace("\n", "\r\n").encode("utf-8"))
    monkeypatch.setattr("taktik.core.database.local.versions.catalog.VERSIONS_DIR", crlf_dir)
    assert MIGRATIONS[0].checksum() == lf


def test_baseline_only_creates_objects_and_carries_no_data():
    statements = split_statements(BASELINE_TEXT)
    assert statements and all(s.upper().startswith("CREATE") for s in statements)
    for label, pattern in build_schema_baseline.FORBIDDEN.items():
        assert not pattern.search(BASELINE_TEXT), label


def test_baseline_holds_only_the_bots_objects():
    """Tables the bot's own steps create (plus sent_dms), indexes on them, views that read only
    them; no trigger and nothing of the desktop app."""
    name = re.compile(r'^CREATE (?:VIRTUAL )?(TABLE|VIEW|TRIGGER) "?(\w+)', re.M)
    created = name.findall(BASELINE_TEXT)
    tables = {n for kind, n in created if kind == "TABLE"}
    views = {n for kind, n in created if kind == "VIEW"}
    assert not [n for kind, n in created if kind == "TRIGGER"]
    bot = build_schema_baseline.bot_steps()
    assert tables <= bot["tables"] | {"sent_dms"}
    assert views <= bot["views"]
    assert views == {"instagram_profiles", "tiktok_profiles"}
    assert not {"app_config", "_sync_state", "media", "profile_qualification", "workflow_schedules",
                "account_device_history", "social_profiles_search"} & tables
    for index_table in re.findall(r"^CREATE (?:UNIQUE )?INDEX \S+ ON \"?(\w+)", BASELINE_TEXT, re.M):
        assert index_table in tables
    conn = sqlite3.connect(":memory:")
    try:
        for statement in split_statements(BASELINE_TEXT):
            conn.execute(statement)
        assert all(isinstance(cols, list) for cols in fingerprint(conn)["views"].values())
    finally:
        conn.close()


def test_bot_steps_add_nothing_the_baseline_lacks():
    """A column or table added to the bot's own un-numbered steps without regenerating
    migration 1 (scripts/build_schema_baseline.py --from-code) fails here."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        from taktik.core.database.local.migrations import run_migrations
        from taktik.core.database.local.schema import create_schema

        create_schema(conn)
        run_migrations(conn)
        steps = fingerprint(conn)
    finally:
        conn.close()
    base = baseline_fingerprint()
    for table, spec in steps["tables"].items():
        if table in base["retired_tables"]:
            continue
        assert table in base["tables"], f"table {table} created by the bot's steps is not in migration 1"
        for column, shape in spec["columns"].items():
            assert base["tables"][table]["columns"].get(column) == shape, f"{table}.{column}"
    for key in steps["unique_keys"]:
        if key.split("(", 1)[0] in base["tables"]:
            assert key in base["unique_keys"], key


def test_baseline_matches_what_the_code_of_both_halves_builds():
    """The 1.9.8 schema rebuilt from the app's migrations.ts and the bot's steps must give
    exactly migration 1: a change to either without `--from-code` fails here."""
    import build_schema_fixpoint

    missing = build_schema_fixpoint.requirements_missing()
    if missing:
        pytest.skip(missing)
    assert build_schema_baseline.check_code() == []


def test_generator_reproduces_the_committed_baseline(tmp_path):
    source = legacy_base(tmp_path / "source.db", seed=False)
    files = build_schema_baseline.generate(source)
    assert files[build_schema_baseline.BASELINE_SQL] == BASELINE_TEXT.replace("\r\n", "\n")
    assert json.loads(files[build_schema_baseline.BASELINE_RETIRED]) == list(MIGRATIONS[0].retired_tables())


def test_split_statements_keeps_trigger_bodies_and_quoted_dashes():
    script = (
        "-- header\nCREATE TABLE t (a TEXT DEFAULT '--not a comment;');\n"
        "CREATE TRIGGER tr AFTER INSERT ON t BEGIN\n  UPDATE t SET a = 'x;y'; -- inner\nEND;\n"
    )
    statements = split_statements(script)
    assert len(statements) == 2
    assert "'--not a comment;'" in statements[0]
    assert statements[1].startswith("CREATE TRIGGER") and "inner" not in statements[1]
    assert strip_comments("SELECT 'a--b' -- c") == "SELECT 'a--b'"


# ─── inspection ───────────────────────────────────────────────────────────────

def test_absent_base_is_reported_and_not_created(tmp_path):
    path = tmp_path / "none" / "taktik-data.db"
    assert inspect_database(path).state == ABSENT
    assert not path.parent.exists()


def test_inspection_of_a_closed_base_creates_no_side_file(tmp_path):
    path = legacy_base(tmp_path / "taktik-data.db")
    before = sha256(path)
    assert side_files(path) == []
    assert inspect_database(path).state == LEGACY_RECOGNIZED
    assert side_files(path) == []
    assert sha256(path) == before


@pytest.mark.parametrize(
    "extra_sql",
    [
        # Column order of an upgraded base (column added by ALTER, so last).
        ["ALTER TABLE device_identity RENAME TO device_identity_old",
         "CREATE TABLE device_identity (created_at TEXT, device_id TEXT, id INTEGER PRIMARY KEY CHECK (id = 1))",
         "DROP TABLE device_identity_old"],
        # Extra unique and plain indexes left by the upgrade branches.
        ["CREATE UNIQUE INDEX idx_extra_sync ON scraping_sessions(sync_id)",
         "CREATE INDEX idx_extra_plain ON accounts(created_at)"],
        # A plain index missing.
        ["DROP INDEX idx_accounts_username_ci"],
        # Whatever the app keeps next to it: other tables, views, triggers, even a broken view.
        ["CREATE TABLE workflow_schedules (id INTEGER PRIMARY KEY)",
         "CREATE VIEW app_view_broken AS SELECT * FROM nowhere",
         "DROP VIEW gmail_accounts"],
    ],
    ids=["column-order", "extra-indexes", "missing-plain-index", "app-objects-ignored"],
)
def test_the_known_1_9_8_shapes_are_recognized(tmp_path, extra_sql):
    path = legacy_base(tmp_path / "taktik-data.db", extra_sql=extra_sql, seed=False)
    status = inspect_database(path)
    assert status.state == LEGACY_RECOGNIZED, status.differences


def test_the_bot_recognizes_a_base_without_any_app_object(tmp_path):
    path = legacy_base(tmp_path / "taktik-data.db", seed=False, app_objects=False)
    assert inspect_database(path).state == LEGACY_RECOGNIZED


@pytest.mark.parametrize(
    "extra_sql, expected",
    [
        (["ALTER TABLE device_identity DROP COLUMN created_at"], "table device_identity: missing columns ['created_at']"),
        (["ALTER TABLE accounts ADD COLUMN added_by_hand TEXT"], "table accounts: unexpected columns ['added_by_hand']"),
        (["DROP INDEX idx_accounts_unified_username"], "missing unique key accounts(platform,username)"),
        (["DROP VIEW instagram_profiles"], "missing view instagram_profiles (absent)"),
        (["CREATE TABLE instagram_accounts (account_id INTEGER PRIMARY KEY, username TEXT)"],
         "retired table instagram_accounts still present"),
        (["DROP VIEW tiktok_profiles", "CREATE TABLE tiktok_profiles (profile_id INTEGER PRIMARY KEY)"],
         "retired table tiktok_profiles still present"),
    ],
    ids=["missing-column", "extra-column", "missing-unique-key", "missing-view", "retired-table",
         "view-still-a-table"],
)
def test_a_base_that_differs_is_not_recognized(tmp_path, extra_sql, expected):
    path = legacy_base(tmp_path / "taktik-data.db", extra_sql=extra_sql, seed=False)
    status = inspect_database(path)
    assert status.state == LEGACY_UNRECOGNIZED
    assert expected in status.differences


# ─── migration ────────────────────────────────────────────────────────────────

def test_new_base_is_created_at_the_target_version(tmp_path):
    path = tmp_path / "sub" / "taktik-data.db"
    result = migrate_database(path, backup_dir=tmp_path / "backups", applied_by="test")
    assert result.success and result.action == "created" and result.backup is None
    assert scalar(path, "PRAGMA user_version") == TARGET
    status = inspect_database(path)
    assert status.state == CURRENT and status.warnings == []
    conn = sqlite3.connect(str(path))
    try:
        assert [(r["version"], r["mode"]) for r in read_journal(conn)] == [(1, "applied")]
        assert compare(target_fingerprint(), fingerprint(conn)) == []
    finally:
        conn.close()


def test_a_current_base_is_left_byte_for_byte(tmp_path):
    path = tmp_path / "taktik-data.db"
    migrate_database(path, backup_dir=tmp_path / "backups")
    before = sha256(path)
    result = migrate_database(path, backup_dir=tmp_path / "backups")
    assert result.success and result.action == "none"
    assert sha256(path) == before
    assert not (tmp_path / "backups").exists()


def test_recognized_legacy_base_is_stamped_without_rewriting(tmp_path):
    path = legacy_base(tmp_path / "taktik-data.db")
    before = objects(path)
    app_before = app_part(path)
    rows_before = scalar(path, "SELECT COUNT(*) FROM accounts")
    result = migrate_database(path, backup_dir=tmp_path / "backups", applied_by="test", clock=FIXED_CLOCK)
    assert result.success and result.action == "stamped" and result.applied == []
    after = objects(path)
    assert {k: v for k, v in after.items() if k[1] != JOURNAL_TABLE and not k[1].startswith("sqlite_autoindex_schema")} == before
    assert set(after) - set(before) == {("table", JOURNAL_TABLE)}
    assert app_part(path) == app_before
    assert scalar(path, "SELECT COUNT(*) FROM accounts") == rows_before
    assert scalar(path, "PRAGMA user_version") == TARGET
    assert scalar(path, "SELECT mode FROM schema_migrations WHERE version = 1") == "stamped"
    backup_path = Path(result.backup["path"])
    assert AUTO_BACKUP_PATTERN.match(backup_path.name)
    assert result.backup["row_counts"]["accounts"] == rows_before
    assert backup_path.name == "taktik-data.v0-v1.20260925-1.db"
    assert scalar(backup_path, "PRAGMA user_version") == 0
    assert objects(backup_path) == before
    second = migrate_database(path, backup_dir=tmp_path / "backups", catalog=_two_step_catalog(
        lambda conn: conn.execute("CREATE TABLE later_step (id INTEGER)")), clock=FIXED_CLOCK)
    assert Path(second.backup["path"]).name == "taktik-data.v1-v2.20260925-2.db"


def test_an_unrecognized_base_goes_to_the_1_9_8_app_before_the_bot_steps(tmp_path):
    """The bot's old steps crash on bases the app has not migrated (in 1.9.8 the app always
    opened first): they only run once the app has passed."""
    path = legacy_base(tmp_path / "taktik-data.db", extra_sql=["DROP INDEX idx_accounts_unified_username"])
    calls = []

    def repair(db_path):
        calls.append(db_path)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE UNIQUE INDEX idx_accounts_unified_username ON accounts(platform, username)")
        conn.commit()
        conn.close()

    before = objects(path)
    first = migrate_database(path, backup_dir=tmp_path / "backups", legacy_steps=repair, clock=FIXED_CLOCK)
    assert not first.success and first.action == "needs_legacy_app"
    assert calls == [] and not first.legacy_steps_ran and first.backup is not None
    assert objects(path) == before

    second = migrate_database(path, backup_dir=tmp_path / "backups", legacy_steps=repair,
                              clock=FIXED_CLOCK, legacy_app_done=True)
    assert second.success and second.action == "stamped" and second.legacy_steps_ran
    assert calls == [str(path)]


def test_bot_steps_that_crash_fail_cleanly_with_the_backup(tmp_path):
    path = legacy_base(tmp_path / "taktik-data.db", extra_sql=["DROP INDEX idx_accounts_unified_username"])

    def crash(_db_path):
        raise sqlite3.OperationalError("no such table: main.instagram_accounts")

    result = migrate_database(path, backup_dir=tmp_path / "backups", legacy_steps=crash, legacy_app_done=True)
    assert not result.success and result.action == "failed" and "instagram_accounts" in result.message
    assert Path(result.backup["path"]).exists()
    assert scalar(path, "PRAGMA user_version") == 0


def test_a_bot_only_base_needs_the_1_9_8_app(tmp_path):
    path = tmp_path / "taktik-data.db"
    from taktik.core.database.local.versions.legacy import run_bot_legacy_steps

    run_bot_legacy_steps(path)
    result = migrate_database(path, backup_dir=tmp_path / "backups", legacy_app_done=True)
    assert not result.success and result.action == "needs_legacy_app"
    assert result.legacy_steps_ran and result.backup is not None
    assert "retired table profile_ai_enrichments still present" in result.differences
    assert scalar(path, "PRAGMA user_version") == 0
    assert scalar(path, f"SELECT COUNT(*) FROM sqlite_master WHERE name = '{JOURNAL_TABLE}'") == 0


def test_a_base_newer_than_the_build_is_never_written(tmp_path):
    path = legacy_base(tmp_path / "taktik-data.db")
    conn = sqlite3.connect(str(path))
    conn.execute(f"PRAGMA user_version = {TARGET + 1}")
    conn.close()
    before = sha256(path)
    assert inspect_database(path).state == TOO_NEW
    result = migrate_database(path, backup_dir=tmp_path / "backups")
    assert not result.success and result.action == "refused"
    assert sha256(path) == before
    assert side_files(path) == []
    assert not (tmp_path / "backups").exists()


def _two_step_catalog(apply_fn, kind=ADDITIVE, rows_unchanged=True):
    return (MIGRATIONS[0], Migration(2, "step_two", kind, apply_fn=apply_fn, rows_unchanged=rows_unchanged))


def test_a_failing_migration_rolls_everything_back(tmp_path):
    path = tmp_path / "taktik-data.db"
    migrate_database(path, backup_dir=tmp_path / "backups")
    before = objects(path)

    def boom(conn):
        conn.execute("CREATE TABLE half_done (id INTEGER)")
        conn.execute("ALTER TABLE accounts ADD COLUMN half_done TEXT")
        raise RuntimeError("injected failure")

    result = migrate_database(path, backup_dir=tmp_path / "backups", catalog=_two_step_catalog(boom))
    assert not result.success and result.action == "failed" and "injected failure" in result.message
    assert scalar(path, "PRAGMA user_version") == 1
    assert objects(path) == before
    assert result.backup is not None and Path(result.backup["path"]).exists()


def test_a_step_that_names_an_app_object_cannot_even_be_built():
    """The target schema is built in memory from the bot's migrations alone: a step that needs an
    app object fails there, before any base is opened."""
    catalog = _two_step_catalog(lambda conn: conn.execute("ALTER TABLE app_config ADD COLUMN sneaky TEXT"))
    with pytest.raises(sqlite3.OperationalError, match="app_config"):
        target_fingerprint(catalog)


@pytest.mark.parametrize(
    "statement",
    [
        "DROP TRIGGER IF EXISTS trg_accounts_touch",
        "DROP VIEW IF EXISTS gmail_accounts",
        "DROP TABLE IF EXISTS app_config",
        "DROP INDEX IF EXISTS idx_account_device_history_account",
    ],
    ids=["app-trigger-on-bot-table", "app-view", "app-table", "app-index"],
)
def test_a_migration_that_touches_an_app_object_is_rolled_back(tmp_path, statement):
    """Harmless in memory (the object is not there), destructive on a real base: stopped."""
    path = legacy_base(tmp_path / "taktik-data.db")
    migrate_database(path, backup_dir=tmp_path / "backups", clock=FIXED_CLOCK)
    before, app_before = objects(path), app_part(path)
    result = migrate_database(path, backup_dir=tmp_path / "backups", clock=FIXED_CLOCK,
                              catalog=_two_step_catalog(lambda conn: conn.execute(statement)))
    assert not result.success and "does not own" in result.message, result.message
    assert scalar(path, "PRAGMA user_version") == 1
    assert objects(path) == before and app_part(path) == app_before


def test_a_rebuild_must_keep_the_app_triggers_of_its_table(tmp_path):
    trigger = ("CREATE TRIGGER trg_filtered_touch AFTER INSERT ON filtered_profiles BEGIN "
               "UPDATE filtered_profiles SET sync_id = 'x' WHERE id = NEW.id; END")
    path = legacy_base(tmp_path / "taktik-data.db", extra_sql=[trigger])
    migrate_database(path, backup_dir=tmp_path / "backups", clock=FIXED_CLOCK)
    before = objects(path)

    def rebuild_losing_triggers(conn):
        conn.execute("CREATE TABLE filtered_profiles_copy AS SELECT * FROM filtered_profiles")
        conn.execute("DROP TABLE filtered_profiles")
        conn.execute("ALTER TABLE filtered_profiles_copy RENAME TO filtered_profiles")

    result = migrate_database(path, backup_dir=tmp_path / "backups", clock=FIXED_CLOCK,
                              catalog=_two_step_catalog(rebuild_losing_triggers, kind=REBUILD))
    assert not result.success
    assert "not the bot's: trigger trg_filtered_touch removed" in result.differences
    assert scalar(path, "PRAGMA user_version") == 1
    assert objects(path) == before


def test_a_process_killed_mid_migration_leaves_the_base_untouched(tmp_path):
    path = tmp_path / "taktik-data.db"
    migrate_database(path, backup_dir=tmp_path / "backups")
    before = objects(path)
    script = tmp_path / "killed.py"
    script.write_text(
        "import os, sys\n"
        "from taktik.core.database.local.versions.catalog import ADDITIVE, MIGRATIONS, Migration\n"
        "from taktik.core.database.local.versions.runner import migrate_database\n"
        "def die(conn):\n"
        "    conn.execute('CREATE TABLE half_done (id INTEGER)')\n"
        "    conn.execute('INSERT INTO accounts (platform, username) VALUES (\\'instagram\\', \\'x\\')')\n"
        "    os._exit(9)\n"
        "catalog = (MIGRATIONS[0], Migration(2, 'dies', ADDITIVE, apply_fn=die))\n"
        "migrate_database(sys.argv[1], backup_dir=sys.argv[2], catalog=catalog)\n",
        encoding="utf-8",
        newline="",
    )
    env = {**os.environ, "PYTHONPATH": str(CORE_ROOT)}
    proc = subprocess.run([sys.executable, str(script), str(path), str(tmp_path / "backups")],
                          cwd=str(CORE_ROOT), env=env, capture_output=True, timeout=120)
    assert proc.returncode == 9, proc.stderr.decode("utf-8", "replace")[-2000:]
    assert scalar(path, "PRAGMA user_version") == 1
    assert objects(path) == before
    assert scalar(path, "SELECT COUNT(*) FROM accounts") == 0
    assert scalar(path, "PRAGMA quick_check") == "ok"


def _rebuild_device_identity(conn):
    conn.execute("CREATE TABLE device_identity_new (id INTEGER PRIMARY KEY CHECK (id = 1), "
                 "device_id TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now')))")
    conn.execute("INSERT INTO device_identity_new SELECT id, device_id, created_at FROM device_identity")
    conn.execute("DROP TABLE device_identity")
    conn.execute("ALTER TABLE device_identity_new RENAME TO device_identity")


def test_a_rebuild_is_rehearsed_on_a_copy_first(tmp_path):
    path = legacy_base(tmp_path / "taktik-data.db")
    migrate_database(path, backup_dir=tmp_path / "backups", clock=FIXED_CLOCK)
    steps = []
    result = migrate_database(path, backup_dir=tmp_path / "backups",
                              catalog=_two_step_catalog(_rebuild_device_identity, kind=REBUILD),
                              on_progress=lambda step, message="": steps.append(step), clock=FIXED_CLOCK)
    assert result.success and result.action == "migrated" and result.applied == [2]
    assert steps.index("backup") < steps.index("rehearsal") < steps.index("apply")
    assert scalar(path, "SELECT device_id FROM device_identity") == "abc"
    assert scalar(path, "PRAGMA user_version") == 2
    assert not list((tmp_path / "backups").glob("*.rehearsal.db*"))


def test_a_rebuild_that_loses_rows_is_stopped_before_touching_the_base(tmp_path):
    path = legacy_base(tmp_path / "taktik-data.db")
    migrate_database(path, backup_dir=tmp_path / "backups", clock=FIXED_CLOCK)
    before = objects(path)

    def lossy(conn):
        _rebuild_device_identity(conn)
        conn.execute("DELETE FROM accounts WHERE platform = 'tiktok'")

    result = migrate_database(path, backup_dir=tmp_path / "backups",
                              catalog=_two_step_catalog(lossy, kind=REBUILD), clock=FIXED_CLOCK)
    assert not result.success and result.action == "failed"
    assert "rows of accounts: 2 -> 1" in result.differences
    assert scalar(path, "PRAGMA user_version") == 1
    assert scalar(path, "SELECT COUNT(*) FROM accounts") == 2
    assert objects(path) == before
    assert not list((tmp_path / "backups").glob("*.rehearsal.db*"))


def test_no_backup_and_no_write_when_the_disk_is_too_full(tmp_path, monkeypatch):
    path = legacy_base(tmp_path / "taktik-data.db")
    before = sha256(path)

    class Usage:
        free = 10

    monkeypatch.setattr(backup_module.shutil, "disk_usage", lambda _p: Usage())
    result = migrate_database(path, backup_dir=tmp_path / "backups")
    assert not result.success and result.action == "refused" and "free space" in result.message
    assert scalar(path, "PRAGMA user_version") == 0
    assert sha256(path) == before
    assert list((tmp_path / "backups").iterdir()) == []


def test_pruning_keeps_the_two_newest_automatic_backups_only(tmp_path):
    names = [
        "taktik-data.v0-v1.20260901-1.db",
        "taktik-data.v1-v2.20260910-1.db",
        "taktik-data.v2-v3.20260910-2.db",
        "taktik-data.v2-v3.20260920-1.db",
    ]
    for name in names:
        (tmp_path / name).write_bytes(b"x")
        (tmp_path / (name + ".json")).write_text("{}", encoding="utf-8")
    manual = ["taktik-data.backup-2026-07-02-pre-geo-backfill.db", "taktik-data.db", "notes.txt"]
    for name in manual:
        (tmp_path / name).write_bytes(b"keep")
    removed = prune_auto_backups(tmp_path)
    assert sorted(removed) == names[:2]
    left = sorted(p.name for p in tmp_path.iterdir())
    assert left == sorted(manual + names[2:] + [n + ".json" for n in names[2:]])


def test_status_warns_when_an_applied_migration_changed(tmp_path):
    path = tmp_path / "taktik-data.db"
    migrate_database(path, backup_dir=tmp_path / "backups")
    conn = sqlite3.connect(str(path))
    conn.execute("UPDATE schema_migrations SET checksum = 'other' WHERE version = 1")
    conn.commit()
    conn.close()
    status = inspect_database(path)
    assert status.state == CURRENT
    assert "migration 1 changed since it was applied" in status.warnings
