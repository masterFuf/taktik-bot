"""ORM-first read cutover (Vague D) — the SQLAlchemy-routed reads must return exactly
the same results as the raw sqlite3 path.

Uses a temp FILE db (the ORM engine opens its own connection, so :memory: would be a
separate empty DB). Builds the real schema, seeds a couple of accounts, then compares
AccountRepository reads with the engine injected (ORM-first) vs without (raw)."""
from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

from taktik.core.database.local.schema import create_schema
from taktik.core.database.local.migrations import run_migrations
from taktik.core.database.orm.engine import create_orm_engine
from taktik.core.database.repositories.instagram.account.account_repository import AccountRepository


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    con = sqlite3.connect(path)
    create_schema(con)
    run_migrations(con)
    # seed two instagram accounts via the raw writer
    repo = AccountRepository(con)
    repo.get_or_create("alice", is_bot=True)
    repo.get_or_create("bob", is_bot=False)
    con.commit()
    con.close()
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


def test_account_reads_orm_first_match_raw(db_path):
    engine = create_orm_engine(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        orm_repo = AccountRepository(conn, engine)   # ORM-first
        raw_repo = AccountRepository(conn, None)      # raw sqlite3

        assert orm_repo.find_all() == raw_repo.find_all()
        assert len(orm_repo.find_all()) == 2

        assert orm_repo.find_by_username("alice") == raw_repo.find_by_username("alice")
        assert orm_repo.find_by_username("alice") is not None
        assert orm_repo.find_by_username("does-not-exist") is None

        aid = orm_repo.find_by_username("alice")["account_id"]
        assert orm_repo.find_by_id(aid) == raw_repo.find_by_id(aid)
        # is_bot is mapped to a real bool on both paths
        assert orm_repo.find_by_username("alice")["is_bot"] is True
        assert orm_repo.find_by_username("bob")["is_bot"] is False
    finally:
        conn.close()
        engine.dispose()


def test_account_reads_fallback_without_engine(db_path):
    """No engine -> reads still work on raw sqlite3 (standalone-bridge bases)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        repo = AccountRepository(conn, None)
        assert len(repo.find_all()) == 2
        assert repo.find_by_username("bob") is not None
    finally:
        conn.close()
