"""
Shared pytest fixtures for the TAKTIK bot test suite.

All DB-related tests use an in-memory or temp-file SQLite database so they
never touch the real %APPDATA% database.
"""
import tempfile
import pathlib
import pytest

from taktik.core.database.local.service import LocalDatabaseService
from taktik.core.database.local.schema import create_schema
from taktik.core.database.local.migrations import run_migrations, _validate_sql_identifier


@pytest.fixture
def tmp_db_path(tmp_path: pathlib.Path) -> str:
    """Return a path to a fresh temporary SQLite file (deleted after test)."""
    return str(tmp_path / "taktik_test.db")


@pytest.fixture
def db(tmp_db_path: str) -> LocalDatabaseService:
    """Return a fully-initialised LocalDatabaseService backed by a temp DB.

    The service is closed automatically after the test.
    """
    svc = LocalDatabaseService(db_path=tmp_db_path)
    yield svc
    svc.close()


@pytest.fixture
def conn(tmp_db_path: str):
    """Return a raw sqlite3 connection with schema + migrations applied.

    Useful for tests that want direct SQL access without the service layer.
    """
    import sqlite3

    con = sqlite3.connect(tmp_db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    create_schema(con)
    run_migrations(con)
    yield con
    con.close()
