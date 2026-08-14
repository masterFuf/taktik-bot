"""Device identity — a stable id for THIS machine, shared by every local writer.

One row, generated once, never updated. Electron runs an identical idempotent
migration (taktik-bot/app/electron/database/migrations.ts), so whichever process opens the
database first creates the identity and the other reuses it.

Why it exists: the database syncs across several PCs (Turso) but rows historically
carried no trace of which device created them — sync maintenance had to guess
ownership from a created_at ≈ interaction_time heuristic. Rows stamped with
origin_device_id (scalar subquery at INSERT) make ownership exact.
"""

from __future__ import annotations

import sqlite3


def run_device_identity_migrations(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_identity (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            device_id TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute(
        "INSERT OR IGNORE INTO device_identity (id, device_id) VALUES (1, lower(hex(randomblob(8))))"
    )
