"""ORM pilot (Vague D) - parity validator for the SQLAlchemy ``app_config`` mapping.

Proves the SQLAlchemy ORM read of ``app_config`` matches the raw ``sqlite3`` read
on a COPY of the real DB, and that mapping the table does NOT mutate the physical
schema (the ORM must never own the schema on the shared dual-runtime base).

Counterpart of front ``scripts/orm-pilot/validate-app-config.cjs``.

Usage: python scripts/orm_pilot/validate_app_config.py [path_to_real_db]
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile

# Allow running from the bot/ root without installing the package.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.orm import Session  # noqa: E402

from taktik.core.database.orm.app_config_entity import AppConfig  # noqa: E402
from taktik.core.database.orm.engine import create_orm_engine  # noqa: E402


def _default_db() -> str:
    return os.path.join(
        os.path.expanduser("~"),
        "AppData", "Roaming", "taktik-desktop", "taktik-data.db",
    )


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    real_db = sys.argv[1] if len(sys.argv) > 1 else _default_db()
    if not os.path.exists(real_db):
        _fail(f"real DB not found: {real_db}")

    copy = os.path.join(tempfile.gettempdir(), "orm_pilot_app_config_bot.db")
    shutil.copyfile(real_db, copy)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(real_db + suffix):
            shutil.copyfile(real_db + suffix, copy + suffix)

    # --- raw sqlite3 read (ground truth) ---
    raw = sqlite3.connect(copy)
    raw.row_factory = sqlite3.Row
    schema_before = raw.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='app_config'"
    ).fetchone()
    schema_before = schema_before[0] if schema_before else None
    raw_rows = raw.execute(
        "SELECT key, value_json, updated_at FROM app_config ORDER BY key"
    ).fetchall()
    raw.close()

    # --- SQLAlchemy ORM read ---
    engine = create_orm_engine(copy)
    with Session(engine) as session:
        orm_rows = session.query(AppConfig).order_by(AppConfig.key).all()
        orm_data = [(r.key, r.value_json, r.updated_at) for r in orm_rows]

    schema_after = None
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='app_config'"
        ).fetchone()
        schema_after = row[0] if row else None
    engine.dispose()

    # --- assertions ---
    if len(raw_rows) != len(orm_data):
        _fail(f"row count mismatch: raw={len(raw_rows)} orm={len(orm_data)}")
    for i, raw_row in enumerate(raw_rows):
        o_key, o_val, o_upd = orm_data[i]
        if raw_row["key"] != o_key:
            _fail(f"key mismatch at {i}: raw={raw_row['key']} orm={o_key}")
        if raw_row["value_json"] != o_val:
            _fail(f"value_json mismatch for key={raw_row['key']}")
        if (raw_row["updated_at"] or None) != (o_upd or None):
            _fail(f"updated_at mismatch for key={raw_row['key']}")
    if schema_before != schema_after:
        _fail("ORM mutated the app_config schema (must map only, never own it)")

    print("PASS: SQLAlchemy app_config read matches raw read")
    print(f"  rows: {len(orm_data)}")
    print(f"  keys: {', '.join(k for k, _, _ in orm_data)}")
    print("  schema unchanged by ORM (mapping only)")


if __name__ == "__main__":
    main()
