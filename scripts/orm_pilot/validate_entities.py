"""ORM pilot (Vague D) - parity validator for the SQLAlchemy mappings.

For each piloted entity, proves the SQLAlchemy ORM read matches the raw ``sqlite3``
read on a COPY of the real DB, and that mapping does NOT mutate the physical schema
(the ORM must never own the schema on the shared dual-runtime base).

Counterpart of front ``scripts/orm-pilot/validate-entities.cjs``.

Usage: python scripts/orm_pilot/validate_entities.py [path_to_real_db]
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.orm import Session  # noqa: E402

from taktik.core.database.orm.engine import create_orm_engine  # noqa: E402
from taktik.core.database.orm.registry import PILOT_ENTITIES  # noqa: E402


def _default_db() -> str:
    return os.path.join(
        os.path.expanduser("~"), "AppData", "Roaming", "taktik-desktop", "taktik-data.db"
    )


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def _schema(conn: sqlite3.Connection, table: str):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row[0] if row else None


def main() -> None:
    real_db = sys.argv[1] if len(sys.argv) > 1 else _default_db()
    if not os.path.exists(real_db):
        _fail(f"real DB not found: {real_db}")

    copy = os.path.join(tempfile.gettempdir(), "orm_pilot_entities_bot.db")
    shutil.copyfile(real_db, copy)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(real_db + suffix):
            shutil.copyfile(real_db + suffix, copy + suffix)

    engine = create_orm_engine(copy)
    for entity, order_col in PILOT_ENTITIES:
        table = entity.__tablename__
        columns = list(entity.__table__.columns.keys())

        raw = sqlite3.connect(copy)
        raw.row_factory = sqlite3.Row
        schema_before = _schema(raw, table)
        col_sql = ", ".join(columns)
        raw_rows = raw.execute(
            f"SELECT {col_sql} FROM {table} ORDER BY {order_col}"
        ).fetchall()
        raw.close()

        with Session(engine) as session:
            orm_rows = (
                session.query(entity)
                .order_by(getattr(entity, order_col))
                .all()
            )

        if len(raw_rows) != len(orm_rows):
            _fail(f"{table}: row count mismatch raw={len(raw_rows)} orm={len(orm_rows)}")
        for i, raw_row in enumerate(raw_rows):
            for c in columns:
                rv = raw_row[c]
                ov = getattr(orm_rows[i], c)
                if (rv if rv is not None else None) != (ov if ov is not None else None):
                    _fail(f"{table}: {c} mismatch at row {i} (orderBy {order_col})")

        raw2 = sqlite3.connect(copy)
        schema_after = _schema(raw2, table)
        raw2.close()
        if schema_before != schema_after:
            _fail(f"{table}: ORM mutated the schema (must map only)")

        print(f"PASS {table}: {len(orm_rows)} rows match raw; schema unchanged")

    engine.dispose()
    print("ALL PASS: SQLAlchemy reads match raw reads; mapping-only honored")


if __name__ == "__main__":
    main()
