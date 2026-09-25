"""The bot's un-numbered bootstrap, kept to bring an old base up to the 1.9.8 schema.

Same steps and connection settings as `LocalDatabaseService` at every opening today.
"""

from __future__ import annotations

import sqlite3


def run_bot_legacy_steps(db_path) -> None:
    from ..migrations import run_migrations
    from ..schema import create_schema

    conn = sqlite3.connect(str(db_path), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        create_schema(conn)
        run_migrations(conn)
    finally:
        conn.close()


__all__ = ["run_bot_legacy_steps"]
