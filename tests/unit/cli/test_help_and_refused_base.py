"""The help of a CLI command opens no base, and a base the CLI may not raise stops it with a sentence.

A group's callback runs before its sub-command reads its own arguments: `taktik device --help` opened
the base, and from source would have migrated it, to print a text.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from taktik.cli import main
from taktik.cli.support import database as cli_database
from taktik.core import database
from taktik.core.database.local import service as service_module
from taktik.core.database.local.versions import opening, runner
from taktik.core.database.local.versions.catalog import VERSIONS_DIR, schema_version
from taktik.core.database.local.versions.opening import UNDER_APP_ENV, UPGRADE_CONSENT_ENV
from taktik.core.database.local.versions.sql_text import split_statements
from unit.paths import CORE

TARGET = schema_version()


@pytest.fixture(autouse=True)
def _from_source_with_no_open_base(monkeypatch):
    opening.forget_checks()
    monkeypatch.setattr(runner, "running_from_source", lambda: True)
    monkeypatch.setattr(service_module, "_local_db_instance", None)
    monkeypatch.setattr(database, "db_service", None)
    monkeypatch.delenv(UNDER_APP_ENV, raising=False)
    monkeypatch.delenv(UPGRADE_CONSENT_ENV, raising=False)
    yield
    opening.forget_checks()


def base_at_version_0(path: Path) -> Path:
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("BEGIN")
    for statement in split_statements((VERSIONS_DIR / "m0001_baseline.sql").read_text(encoding="utf-8")):
        conn.execute(statement)
    conn.execute("COMMIT")
    conn.close()
    return path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def forbid_opening(monkeypatch):
    def forbidden():
        raise AssertionError("the help opened the base")

    monkeypatch.setattr(cli_database, "configure_db_service", forbidden)


@pytest.mark.parametrize("arguments", [
    ["device", "--help"],
    ["tiktok", "launch", "--help"],
    ["workflows", "--help"],
])
def test_the_help_of_a_command_opens_no_base(monkeypatch, arguments):
    forbid_opening(monkeypatch)

    result = CliRunner().invoke(main.cli, ["--lang", "en", *arguments])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.stdout


def test_the_help_of_the_tiktok_entry_point_opens_no_base(monkeypatch):
    forbid_opening(monkeypatch)

    result = CliRunner().invoke(main.tiktok, ["launch", "--help"])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.stdout


def test_the_real_help_leaves_a_base_behind_as_it_found_it(tmp_path):
    """The whole process, as an operator runs it: no in-process stand-in for the opening."""
    path = base_at_version_0(tmp_path / "taktik-data.db")
    sha_before, files_before = sha256(path), sorted(os.listdir(tmp_path))
    env = {**os.environ, "TAKTIK_DB_PATH": str(path), "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(CORE)}
    env.pop(UNDER_APP_ENV, None)
    env.pop(UPGRADE_CONSENT_ENV, None)

    run = subprocess.run([sys.executable, "-m", "taktik", "device", "--help"],
                         cwd=str(CORE), env=env, capture_output=True, timeout=180)

    assert run.returncode == 0, run.stderr.decode("utf-8", "replace")[-2000:]
    assert sha256(path) == sha_before
    assert sorted(entry for entry in os.listdir(tmp_path) if entry != "logs") == files_before


@pytest.mark.parametrize("lang, sentence", [
    ("en", "can no longer open"),
    ("fr", "ne pourra plus l'ouvrir"),
])
def test_a_base_behind_stops_the_cli_with_a_sentence_and_changes_nothing(tmp_path, monkeypatch, lang, sentence):
    path = base_at_version_0(tmp_path / "taktik-data.db")
    sha_before = sha256(path)
    monkeypatch.setenv("TAKTIK_DB_PATH", str(path))

    # An option a command refuses: the group's callback runs, the command itself does nothing.
    result = CliRunner().invoke(main.cli, ["--lang", lang, "device", "--not-an-option"])

    assert result.exit_code == 1, result.output
    assert sentence in result.stderr
    assert f"{UPGRADE_CONSENT_ENV}={TARGET}" in result.stderr
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert sha256(path) == sha_before
    assert not (tmp_path / "backups").exists()
    assert not [name for name in os.listdir(tmp_path) if name.endswith(("-wal", "-shm"))]


def test_with_the_consent_the_cli_goes_on_and_raises_it(tmp_path, monkeypatch):
    path = base_at_version_0(tmp_path / "taktik-data.db")
    monkeypatch.setenv("TAKTIK_DB_PATH", str(path))
    monkeypatch.setenv(UPGRADE_CONSENT_ENV, str(TARGET))

    result = CliRunner().invoke(main.cli, ["--lang", "en", "device", "--not-an-option"])

    assert str(path) in result.stderr
    conn = sqlite3.connect(str(path))
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == TARGET
    finally:
        conn.close()
    assert list((tmp_path / "backups").glob("taktik-data.v0-v*.db"))
