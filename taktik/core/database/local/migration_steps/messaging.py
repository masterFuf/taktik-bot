"""Messaging (DM) migration steps."""

from __future__ import annotations

import sqlite3

from loguru import logger


def run_messaging_migrations(cursor: sqlite3.Cursor) -> None:
    """Additive, idempotent migrations for the DM tables.

    ``displayed_at`` holds the raw IG date/time label for display (e.g. "Jun 12,
    10:29 AM"); ``sent_at`` stays a sortable insertion datetime (sync delta cursor).
    Older databases (created before this column) get it backfilled-as-NULL via ALTER.
    """
    def _table_exists(name: str) -> bool:
        return cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    if not _table_exists("dm_messages"):
        return  # fresh DB: create_messaging_tables already includes displayed_at

    try:
        cursor.execute("SELECT displayed_at FROM dm_messages LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding displayed_at to dm_messages")
        cursor.execute("ALTER TABLE dm_messages ADD COLUMN displayed_at TEXT")
