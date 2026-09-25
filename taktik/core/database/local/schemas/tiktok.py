"""TikTok schema definitions."""

from __future__ import annotations

import sqlite3


def create_tiktok_tables(cursor: sqlite3.Cursor) -> None:
    """Create TikTok tables."""
    # tiktok_accounts folded into the unified accounts table (Vague B). Not created any more:
    # run_accounts_unification_migrations only drains and drops it on bases that still carry it.

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
