"""Schema bridge: path resolution, events, exit codes, and a run through the real launcher."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from bridges.database import schema as schema_bridge
from taktik.core.database.local.versions.catalog import VERSIONS_DIR, schema_version
from taktik.core.database.local.versions.sql_text import split_statements

CORE_ROOT = Path(__file__).resolve().parents[4]
TARGET = schema_version()


class FakeIpc:
    def __init__(self):
        self.events = []

    def send(self, msg_type, **kwargs):
        self.events.append({"type": msg_type, **kwargs})

    def error(self, error, error_code=None, **extra):
        self.events.append({"type": "error", "error": error, "error_code": error_code})

    def of(self, msg_type):
        return [e for e in self.events if e["type"] == msg_type]


def legacy_base(path: Path) -> Path:
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("BEGIN")
    for statement in split_statements((VERSIONS_DIR / "m0001_baseline.sql").read_text(encoding="utf-8")):
        conn.execute(statement)
    conn.execute("INSERT INTO accounts (platform, username) VALUES ('instagram', 'compte_test')")
    conn.execute("COMMIT")
    conn.close()
    return path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def no_env_db(monkeypatch):
    monkeypatch.delenv("TAKTIK_DB_PATH", raising=False)


def test_cli_path_and_env_path_must_name_the_same_file(tmp_path):
    same = str(tmp_path / "taktik-data.db")
    assert schema_bridge.resolve_db_path(same, {"TAKTIK_DB_PATH": same}) == same
    assert schema_bridge.resolve_db_path(None, {"TAKTIK_DB_PATH": same}) == same
    with pytest.raises(schema_bridge.DbPathMismatch):
        schema_bridge.resolve_db_path(same, {"TAKTIK_DB_PATH": str(tmp_path / "other.db")})


def test_mismatched_paths_are_refused_before_anything_is_opened(tmp_path, monkeypatch):
    monkeypatch.setenv("TAKTIK_DB_PATH", str(tmp_path / "other.db"))
    ipc = FakeIpc()
    code = schema_bridge.run({"command": "migrate", "db": str(tmp_path / "taktik-data.db")}, ipc=ipc)
    assert code == schema_bridge.EXIT_REFUSED
    assert ipc.of("error")[0]["error_code"] == "SCHEMA_DB_PATH_MISMATCH"
    assert list(tmp_path.iterdir()) == []


def test_status_reports_and_writes_nothing(tmp_path, no_env_db):
    path = legacy_base(tmp_path / "taktik-data.db")
    before = sha256(path)
    ipc = FakeIpc()
    code = schema_bridge.run({"command": "status", "db": str(path)}, ipc=ipc)
    assert code == schema_bridge.EXIT_OK
    status = ipc.of("schema_status")[0]["status"]
    assert status["state"] == "legacy_recognized" and status["target_version"] == TARGET
    assert sha256(path) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["taktik-data.db"]


def test_status_of_an_absent_base_does_not_create_it(tmp_path, no_env_db):
    ipc = FakeIpc()
    code = schema_bridge.run({"command": "status", "db": str(tmp_path / "taktik-data.db")}, ipc=ipc)
    assert code == schema_bridge.EXIT_OK
    assert ipc.of("schema_status")[0]["status"]["state"] == "absent"
    assert list(tmp_path.iterdir()) == []


def test_migrate_stamps_and_reports_progress_and_backup(tmp_path, no_env_db):
    path = legacy_base(tmp_path / "taktik-data.db")
    ipc = FakeIpc()
    code = schema_bridge.run({"command": "migrate", "db": str(path), "backupDir": str(tmp_path / "backups")}, ipc=ipc)
    assert code == schema_bridge.EXIT_OK
    steps = [e["step"] for e in ipc.of("schema_progress")]
    assert steps[:2] == ["backup", "apply"]
    result = ipc.of("schema_result")[0]
    assert result["success"] and result["action"] == "stamped" and result["to_version"] == TARGET
    assert Path(result["backup"]["path"]).exists() and "row_counts" not in result["backup"]


def test_a_base_newer_than_the_build_is_refused(tmp_path, no_env_db):
    path = legacy_base(tmp_path / "taktik-data.db")
    conn = sqlite3.connect(str(path))
    conn.execute(f"PRAGMA user_version = {TARGET + 1}")
    conn.close()
    before = sha256(path)
    ipc = FakeIpc()
    assert schema_bridge.run({"command": "status", "db": str(path)}, ipc=ipc) == schema_bridge.EXIT_REFUSED
    assert schema_bridge.run({"command": "migrate", "db": str(path)}, ipc=ipc) == schema_bridge.EXIT_REFUSED
    assert ipc.of("schema_result")[0]["action"] == "refused"
    assert sha256(path) == before


def test_after_legacy_app_lets_the_bot_steps_run(tmp_path, no_env_db):
    path = tmp_path / "taktik-data.db"
    from taktik.core.database.local.versions.legacy import run_bot_legacy_steps

    run_bot_legacy_steps(path)
    ipc = FakeIpc()
    config = {"command": "migrate", "db": str(path), "backupDir": str(tmp_path / "backups")}
    assert schema_bridge.run(config, ipc=ipc) == schema_bridge.EXIT_NEEDS_LEGACY_APP
    assert not ipc.of("schema_result")[0]["legacy_steps_ran"]
    ipc = FakeIpc()
    assert schema_bridge.run({**config, "afterLegacyApp": True}, ipc=ipc) == schema_bridge.EXIT_NEEDS_LEGACY_APP
    result = ipc.of("schema_result")[0]
    assert result["legacy_steps_ran"] and result["difference_count"] > 0


def test_bad_usage_is_an_error_event(tmp_path, no_env_db):
    ipc = FakeIpc()
    assert schema_bridge.run({"command": "explode"}, ipc=ipc) == schema_bridge.EXIT_FAILED
    assert ipc.of("error")[0]["error_code"] == "SCHEMA_USAGE"
    assert schema_bridge.run({}, ipc=ipc) == schema_bridge.EXIT_FAILED


def test_no_config_file_is_a_usage_error_through_the_launcher(tmp_path):
    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP", "USERPROFILE") if key in os.environ}
    env.update({"PYTHONIOENCODING": "utf-8", "TAKTIK_DB_PATH": str(tmp_path / "taktik-data.db")})
    proc = subprocess.run(
        [sys.executable, str(CORE_ROOT / "bridges" / "launcher.py"), "schema_bridge"],
        cwd=str(CORE_ROOT), env=env, capture_output=True, timeout=180,
    )
    events = [json.loads(line) for line in proc.stdout.decode("utf-8").splitlines() if line.strip()]
    assert proc.returncode == 1
    assert [(e["type"], e.get("error_code")) for e in events] == [("error", "SCHEMA_USAGE")]
    assert not (tmp_path / "taktik-data.db").exists()


def _launch(config, env_extra, tmp_path):
    config_path = tmp_path / f"schema_{config['command']}.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP", "USERPROFILE") if key in os.environ}
    env.update({"PYTHONIOENCODING": "utf-8", **env_extra})
    proc = subprocess.run(
        [sys.executable, str(CORE_ROOT / "bridges" / "launcher.py"), "schema_bridge", str(config_path)],
        cwd=str(CORE_ROOT), env=env, capture_output=True, timeout=180,
    )
    lines = [line for line in proc.stdout.decode("utf-8").splitlines() if line.strip()]
    return proc.returncode, [json.loads(line) for line in lines]


def test_through_the_launcher_with_the_allowlisted_environment(tmp_path):
    """The way the desktop app will run it: launcher, TAKTIK_DB_PATH, JSON lines only on stdout."""
    path = tmp_path / "taktik-data.db"
    code, events = _launch({"command": "migrate", "backupDir": str(tmp_path / "backups")},
                           {"TAKTIK_DB_PATH": str(path)}, tmp_path)
    assert code == 0, events
    assert [e["type"] for e in events][0] == "schema_status"
    result = [e for e in events if e["type"] == "schema_result"][0]
    assert result["action"] == "created" and result["db_path"] == str(path)

    code, events = _launch({"command": "status"}, {"TAKTIK_DB_PATH": str(path)}, tmp_path)
    assert code == 0 and events == [e for e in events if e["type"] == "schema_status"]
    assert events[0]["status"]["state"] == "current"
