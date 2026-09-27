"""The CLI says which database it opens, before it does anything with it.

A CLI run writes its facts (sessions, interactions, sent DMs) to the desktop app's own database
unless `TAKTIK_DB_PATH` names another: nothing on screen said so. The path goes to stderr, so a
command whose stdout a script reads keeps it clean.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from taktik.cli import main


@pytest.fixture
def opened(monkeypatch, tmp_path):
    path = str(tmp_path / "throwaway.db")
    monkeypatch.setattr(main, "configure_db_service",
                        lambda: SimpleNamespace(local_db=SimpleNamespace(db_path=path)))
    return path


def test_the_path_it_opens_is_on_stderr(opened, monkeypatch):
    monkeypatch.setenv("TAKTIK_DB_PATH", opened)

    result = CliRunner().invoke(main.cli, ["--lang", "en", "device", "--help"])

    assert result.exit_code == 0, result.output
    assert opened in result.stderr
    assert opened not in result.stdout


def test_without_taktik_db_path_it_says_it_is_the_app_database(opened, monkeypatch):
    monkeypatch.delenv("TAKTIK_DB_PATH", raising=False)

    result = CliRunner().invoke(main.cli, ["--lang", "en", "device", "--help"])

    assert opened in result.stderr
    assert "TAKTIK_DB_PATH" in result.stderr


def test_the_tiktok_entry_point_says_it_too(opened, monkeypatch):
    from taktik.core import database

    monkeypatch.setattr(database, "db_service", None)
    monkeypatch.setenv("TAKTIK_DB_PATH", opened)

    result = CliRunner().invoke(main.tiktok, ["launch", "--help"])

    assert opened in result.stderr
