"""TikTok schema definitions."""

from __future__ import annotations

import sqlite3


def create_tiktok_tables(cursor: sqlite3.Cursor) -> None:
    """Create TikTok tables."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tiktok_accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT,
            is_bot INTEGER DEFAULT 1,
            user_id INTEGER,
            license_id INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tiktok_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT DEFAULT '',
            followers_count INTEGER DEFAULT 0,
            following_count INTEGER DEFAULT 0,
            likes_count INTEGER DEFAULT 0,
            videos_count INTEGER DEFAULT 0,
            is_private INTEGER DEFAULT 0,
            is_verified INTEGER DEFAULT 0,
            biography TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)


    # tiktok_sessions removed (Vague B Phase C): folded into sessions_unified; dropped by run_migrations.

    # tiktok_filtered_profiles folded into the unified filtered_profiles (platform axis, Vague B).

    # tiktok_scraped_profiles folded into the unified scraped_profiles (platform axis, Vague B).


def create_tiktok_indexes(cursor: sqlite3.Cursor) -> None:
    """Create TikTok indexes."""
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_accounts_username ON tiktok_accounts(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_profiles_username ON tiktok_profiles(username)")
