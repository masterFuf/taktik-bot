"""Gmail account schema definitions."""

from __future__ import annotations

import sqlite3


def create_gmail_tables(cursor: sqlite3.Cursor) -> None:
    """Create Gmail account tables and indexes."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gmail_accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            device_id TEXT,
            last_used_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_accounts_email ON gmail_accounts(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_accounts_device ON gmail_accounts(device_id)")
