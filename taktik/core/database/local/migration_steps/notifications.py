"""Notifications migration steps."""

from __future__ import annotations

import sqlite3

from ..schemas.notifications import create_notifications_tables, create_notifications_indexes


def run_notifications_migrations(cursor: sqlite3.Cursor) -> None:
    """Additive, idempotent migration for the cross-platform notifications table.

    Brand-new table: ``CREATE TABLE IF NOT EXISTS`` + indexes also covers existing
    databases (they simply gain the table on next boot). Later column adds should use
    the ``try SELECT col / except OperationalError -> ALTER ADD COLUMN`` pattern (see
    ``messaging.py``).
    """
    create_notifications_tables(cursor)
    create_notifications_indexes(cursor)


__all__ = ["run_notifications_migrations"]
