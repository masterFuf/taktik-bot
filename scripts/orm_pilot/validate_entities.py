"""ORM pilot (Vague D) - parity validator for the SQLAlchemy mappings.

For each piloted entity, proves the SQLAlchemy ORM read matches the raw ``sqlite3``
read on a COPY of the real DB, and that mapping does NOT mutate the physical schema
(the ORM must never own the schema on the shared dual-runtime base).

Counterpart of front ``scripts/orm-pilot/validate-entities.cjs``.

Checks column parity FIRST (every table column mapped, every mapped column real), then
the read equivalence. The value comparison alone is blind to a column the entity forgot.

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


def _check_column_parity(db_path: str) -> None:
    """Every mapped column exists in the table, and every table column is mapped.

    Comparing only the MAPPED columns (what the value check below does) cannot see a
    column the entity forgot: the read succeeds, the field is simply absent from the
    object. That blind spot had let fourteen columns drift across four entities --
    ``interactions`` alone was missing five, including ``session_sync_id``.

    Every mismatch is reported before exiting, so one drifted table does not hide the
    others. Same contract as the front twin, ``scripts/orm-pilot/validate-entities.cjs``.
    """
    conn = sqlite3.connect(db_path)
    failures = []
    try:
        for entity, _order_col in PILOT_ENTITIES:
            table = entity.__tablename__
            mapped = list(entity.__table__.columns.keys())
            real = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if not real:
                failures.append(f"{table}: not present in DB (entity maps a missing table)")
                continue
            missing = [c for c in mapped if c not in real]
            extra = [c for c in real if c not in mapped]
            if missing:
                failures.append(
                    f"{table}: entity maps columns absent from DB: {', '.join(missing)}"
                )
            if extra:
                failures.append(
                    f"{table}: DB columns not mapped by entity: {', '.join(extra)}"
                )
    finally:
        conn.close()

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        _fail(f"{len(failures)} column-parity mismatch(es) across {len(PILOT_ENTITIES)} entities")
    print(f"PASS column parity: {len(PILOT_ENTITIES)} entities map their table columns exactly")


def main() -> None:
    real_db = sys.argv[1] if len(sys.argv) > 1 else _default_db()
    if not os.path.exists(real_db):
        _fail(f"real DB not found: {real_db}")

    copy = os.path.join(tempfile.gettempdir(), "orm_pilot_entities_bot.db")
    shutil.copyfile(real_db, copy)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(real_db + suffix):
            shutil.copyfile(real_db + suffix, copy + suffix)

    _check_column_parity(copy)

    row_cap = 3000  # big tables: full count + first N rows compared
    engine = create_orm_engine(copy)
    for entity, order_col in PILOT_ENTITIES:
        table = entity.__tablename__
        columns = list(entity.__table__.columns.keys())

        raw = sqlite3.connect(copy)
        raw.row_factory = sqlite3.Row
        schema_before = _schema(raw, table)
        total = raw.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        col_sql = ", ".join(columns)
        raw_rows = raw.execute(
            f"SELECT {col_sql} FROM {table} ORDER BY {order_col} LIMIT ?", (row_cap,)
        ).fetchall()
        raw.close()

        with Session(engine) as session:
            orm_count = session.query(entity).count()
            orm_rows = (
                session.query(entity)
                .order_by(getattr(entity, order_col))
                .limit(row_cap)
                .all()
            )

        if orm_count != total:
            _fail(f"{table}: count mismatch raw={total} orm={orm_count}")
        if len(raw_rows) != len(orm_rows):
            _fail(f"{table}: sampled row count mismatch raw={len(raw_rows)} orm={len(orm_rows)}")
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

        note = f" (compared first {len(raw_rows)}/{total})" if total > len(raw_rows) else ""
        print(f"PASS {table}: count {orm_count} matches; rows match raw{note}; schema unchanged")

    engine.dispose()
    print("ALL PASS: SQLAlchemy reads match raw reads; mapping-only honored")


if __name__ == "__main__":
    main()
