"""`schema_migrations`: which numbered migration reached this base, how and when.

`PRAGMA user_version` is the truth; this table is the history kept for support.
"""

from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional

from .catalog import Migration

JOURNAL_TABLE = "schema_migrations"

JOURNAL_DDL = """CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    checksum TEXT NOT NULL,
    mode TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    applied_by TEXT,
    backup_path TEXT,
    duration_ms INTEGER
)"""

APPLIED = "applied"
STAMPED = "stamped"


def ensure_journal(conn: sqlite3.Connection) -> None:
    conn.execute(JOURNAL_DDL)


def read_journal(conn: sqlite3.Connection) -> List[Dict]:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (JOURNAL_TABLE,)
    ).fetchone()
    if not exists:
        return []
    cursor = conn.execute(
        "SELECT version, name, kind, checksum, mode, applied_at, applied_by, backup_path, duration_ms "
        "FROM schema_migrations ORDER BY version"
    )
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def record_migration(
    conn: sqlite3.Connection,
    migration: Migration,
    mode: str,
    applied_by: str,
    backup_path: Optional[str],
    duration_ms: int,
) -> None:
    conn.execute(
        "INSERT INTO schema_migrations (version, name, kind, checksum, mode, applied_by, backup_path, duration_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (migration.version, migration.name, migration.kind, migration.checksum(), mode,
         applied_by, backup_path, duration_ms),
    )


__all__ = [
    "APPLIED",
    "JOURNAL_DDL",
    "JOURNAL_TABLE",
    "STAMPED",
    "ensure_journal",
    "read_journal",
    "record_migration",
]
