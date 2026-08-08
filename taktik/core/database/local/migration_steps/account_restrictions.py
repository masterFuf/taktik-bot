"""Account restriction signals migration steps."""

from __future__ import annotations

import sqlite3

from ..schemas.account_restrictions import (
    create_account_restriction_tables,
    create_account_restriction_indexes,
)


def run_account_restriction_migrations(cursor: sqlite3.Cursor) -> None:
    """Additive, idempotent migration for the account restriction signals table.

    Brand-new table: ``CREATE TABLE IF NOT EXISTS`` + indexes also covers existing
    databases (they gain the table on next boot). Later column adds should use the
    ``try SELECT col / except OperationalError -> ALTER ADD COLUMN`` pattern.
    """
    create_account_restriction_tables(cursor)
    create_account_restriction_indexes(cursor)


__all__ = ["run_account_restriction_migrations"]
