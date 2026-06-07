"""ORM pilot (Vague D): SQLAlchemy maps app_config without owning the schema.

Self-contained (temp-file DB, no real base): the table is created by raw SQL
(standing in for the physical migrations), then mapped + read via SQLAlchemy and
compared to a raw sqlite3 read. Asserts the ORM never mutates the schema.
"""
import os
import sqlite3
import tempfile

import pytest

from taktik.core.database.orm.app_config_entity import AppConfig
from taktik.core.database.orm.engine import create_orm_engine
from sqlalchemy.orm import Session


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE app_config (key TEXT PRIMARY KEY, "
        "value_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT DEFAULT (datetime('now')))"
    )
    con.executemany(
        "INSERT INTO app_config (key, value_json, updated_at) VALUES (?, ?, ?)",
        [
            ("device_groups", '{"groups": []}', "2026-06-07T10:00:00"),
            ("network_pools", '{"pools": []}', "2026-06-07T11:00:00"),
        ],
    )
    con.commit()
    con.close()
    yield path
    os.remove(path)


def _schema(path):
    con = sqlite3.connect(path)
    try:
        row = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='app_config'"
        ).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def test_sqlalchemy_read_matches_raw(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    raw = con.execute(
        "SELECT key, value_json, updated_at FROM app_config ORDER BY key"
    ).fetchall()
    con.close()

    engine = create_orm_engine(db_path)
    with Session(engine) as session:
        orm = session.query(AppConfig).order_by(AppConfig.key).all()
    engine.dispose()

    assert [r["key"] for r in raw] == [r.key for r in orm]
    assert [r["value_json"] for r in raw] == [r.value_json for r in orm]
    assert [r["updated_at"] for r in raw] == [r.updated_at for r in orm]


def test_mapping_does_not_mutate_schema(db_path):
    before = _schema(db_path)
    engine = create_orm_engine(db_path)
    with Session(engine) as session:
        session.query(AppConfig).all()
    engine.dispose()
    assert _schema(db_path) == before
