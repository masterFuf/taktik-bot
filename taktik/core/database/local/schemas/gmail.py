"""Gmail account schema definitions."""

from __future__ import annotations

import sqlite3


def create_gmail_tables(cursor: sqlite3.Cursor) -> None:
    """Bootstrap the legacy ``gmail_accounts`` shape (fresh/standalone bases).

    Vague F2 folds ``gmail_accounts`` into the unified ``accounts`` table +
    ``account_device_history`` and turns ``gmail_accounts`` into a read-only compat
    VIEW (``run_gmail_accounts_fold`` in migrations). On an existing base where the
    fold already ran, this ``CREATE TABLE IF NOT EXISTS`` no-ops over the same-named
    view; on a fresh base it creates the table which the fold then converts to the
    view in the same boot. No indexes here ("views may not be indexed" once folded).
    """
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gmail_accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            device_id TEXT,
            last_used_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
