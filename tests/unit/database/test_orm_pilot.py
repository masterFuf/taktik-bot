"""ORM pilot (Vague D): SQLAlchemy maps the piloted tables without owning the schema.

Self-contained (temp-file DB, no real base): the tables are created by raw SQL
(standing in for the physical migrations), then mapped + read via SQLAlchemy and
compared to a raw sqlite3 read. Asserts the ORM never mutates the schema. Iterates
the entity registry so new pilot entities are covered automatically.
"""
import os
import sqlite3
import tempfile

import pytest
from sqlalchemy.orm import Session

from taktik.core.database.orm.engine import create_orm_engine
from taktik.core.database.orm.registry import PILOT_ENTITIES

# Minimal raw DDL + seed rows mirroring the real (migration-owned) schema.
_FIXTURE = {
    "app_config": {
        "ddl": (
            "CREATE TABLE app_config (key TEXT PRIMARY KEY, "
            "value_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT)"
        ),
        "rows": [
            ("INSERT INTO app_config (key, value_json, updated_at) VALUES (?,?,?)",
             [("device_groups", '{"groups": []}', "2026-06-07T10:00:00"),
              ("network_pools", '{"pools": []}', "2026-06-07T11:00:00")]),
        ],
    },
    "interactions": {
        "ddl": (
            "CREATE TABLE interactions (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "platform TEXT NOT NULL DEFAULT 'instagram', legacy_id INTEGER, "
            "session_id INTEGER, account_id INTEGER, profile_id INTEGER, "
            "interaction_type TEXT NOT NULL, success INTEGER DEFAULT 1, content TEXT, "
            "video_id TEXT, interaction_time TEXT, created_at TEXT, sync_id TEXT)"
        ),
        "rows": [
            ("INSERT INTO interactions (platform, interaction_type, success, account_id) "
             "VALUES (?,?,?,?)",
             [("instagram", "like", 1, 7), ("tiktok", "follow", 0, 2)]),
        ],
    },
}


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    for spec in _FIXTURE.values():
        con.execute(spec["ddl"])
        for sql, params in spec["rows"]:
            con.executemany(sql, params)
    con.commit()
    con.close()
    yield path
    os.remove(path)


def _schema(path, table):
    con = sqlite3.connect(path)
    try:
        row = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        return row[0] if row else None
    finally:
        con.close()


@pytest.mark.parametrize("entity,order_col", PILOT_ENTITIES)
def test_orm_read_matches_raw(db_path, entity, order_col):
    table = entity.__tablename__
    columns = list(entity.__table__.columns.keys())

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    raw = con.execute(
        f"SELECT {', '.join(columns)} FROM {table} ORDER BY {order_col}"
    ).fetchall()
    con.close()

    engine = create_orm_engine(db_path)
    with Session(engine) as session:
        orm = session.query(entity).order_by(getattr(entity, order_col)).all()
    engine.dispose()

    assert len(raw) == len(orm)
    for i, raw_row in enumerate(raw):
        for c in columns:
            assert raw_row[c] == getattr(orm[i], c), f"{table}.{c} mismatch at row {i}"


@pytest.mark.parametrize("entity,order_col", PILOT_ENTITIES)
def test_mapping_does_not_mutate_schema(db_path, entity, order_col):
    table = entity.__tablename__
    before = _schema(db_path, table)
    engine = create_orm_engine(db_path)
    with Session(engine) as session:
        session.query(entity).all()
    engine.dispose()
    assert _schema(db_path, table) == before
