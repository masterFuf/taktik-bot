"""ORM pilot (Vague D): SQLAlchemy mappings are valid and map without owning the schema.

Two layers of coverage:
  - read-match: for the tables with an explicit fixture (app_config, interactions),
    the SQLAlchemy read matches a raw sqlite3 read and mapping never mutates the schema;
  - mappability: every registered entity (PILOT_ENTITIES) can be created from its model
    and queried without a SQLAlchemy configuration error.

Column-parity against the REAL migration schema is covered by
scripts/orm_pilot/validate_entities.py (run against a copy of the live DB).
"""
import os
import sqlite3
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from taktik.core.database.orm.base import Base
from taktik.core.database.orm.engine import create_orm_engine
from taktik.core.database.orm.registry import PILOT_ENTITIES

# Tables with an explicit raw fixture (DDL + seed) for read-match coverage.
_FIXTURE = {
    "app_config": {
        "ddl": (
            "CREATE TABLE app_config (key TEXT PRIMARY KEY, "
            "value_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT)"
        ),
        "seed": [
            ("INSERT INTO app_config (key, value_json, updated_at) VALUES (?,?,?)",
             [("device_groups", '{"groups": []}', "2026-06-07T10:00:00"),
              ("network_pools", '{"pools": []}', "2026-06-07T11:00:00")]),
        ],
        "order_by": "key",
    },
    "interactions": {
        "ddl": (
            "CREATE TABLE interactions (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "platform TEXT NOT NULL DEFAULT 'instagram', legacy_id INTEGER, "
            "session_id INTEGER, account_id INTEGER, profile_id INTEGER, "
            "interaction_type TEXT NOT NULL, success INTEGER DEFAULT 1, content TEXT, "
            "video_id TEXT, interaction_time TEXT, created_at TEXT, sync_id TEXT)"
        ),
        "seed": [
            ("INSERT INTO interactions (platform, interaction_type, success, account_id) "
             "VALUES (?,?,?,?)",
             [("instagram", "like", 1, 7), ("tiktok", "follow", 0, 2)]),
        ],
        "order_by": "id",
    },
}

_ENTITY_BY_TABLE = {e.__tablename__: e for e, _ in PILOT_ENTITIES}


@pytest.fixture
def fixture_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    for spec in _FIXTURE.values():
        con.execute(spec["ddl"])
        for sql, params in spec["seed"]:
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


@pytest.mark.parametrize("table", list(_FIXTURE))
def test_read_matches_raw_and_schema_unchanged(fixture_db, table):
    entity = _ENTITY_BY_TABLE[table]
    order_col = _FIXTURE[table]["order_by"]
    columns = list(entity.__table__.columns.keys())

    con = sqlite3.connect(fixture_db)
    con.row_factory = sqlite3.Row
    raw = con.execute(
        f"SELECT {', '.join(columns)} FROM {table} ORDER BY {order_col}"
    ).fetchall()
    con.close()

    before = _schema(fixture_db, table)
    engine = create_orm_engine(fixture_db)
    with Session(engine) as session:
        orm = session.query(entity).order_by(getattr(entity, order_col)).all()
    engine.dispose()

    assert len(raw) == len(orm)
    for i, raw_row in enumerate(raw):
        for c in columns:
            assert raw_row[c] == getattr(orm[i], c), f"{table}.{c} mismatch at row {i}"
    assert _schema(fixture_db, table) == before


@pytest.mark.parametrize("entity,order_col", PILOT_ENTITIES)
def test_entity_is_mappable_and_queryable(entity, order_col):
    """Every registered entity can be created from its model and queried (catches
    SQLAlchemy mapping/config errors). Uses an isolated in-memory-ish temp DB."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        engine = create_engine(f"sqlite:///{path}")
        entity.__table__.create(engine)  # create THIS table from the model (test only)
        with Session(engine) as session:
            rows = session.query(entity).order_by(getattr(entity, order_col)).all()
        engine.dispose()
        assert rows == []
    finally:
        os.remove(path)
