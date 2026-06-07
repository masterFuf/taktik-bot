"""Instagram core schema definitions."""

from __future__ import annotations

import sqlite3


def create_instagram_tables(cursor: sqlite3.Cursor) -> None:
    """Create Instagram core tables."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS instagram_accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            is_bot INTEGER DEFAULT 1,
            user_id INTEGER,
            license_id INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS instagram_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            full_name TEXT DEFAULT '',
            biography TEXT,
            followers_count INTEGER DEFAULT 0,
            following_count INTEGER DEFAULT 0,
            posts_count INTEGER DEFAULT 0,
            is_private INTEGER DEFAULT 0,
            is_verified INTEGER DEFAULT 0,
            is_business INTEGER DEFAULT 0,
            business_category TEXT,
            website TEXT,
            linked_accounts TEXT,
            profile_pic_path TEXT,
            location_city TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)


    # Unified filtered_profiles (platform axis: instagram + tiktok). No cross-table FK
    # since profile_id / account_id are polymorphic across platforms; uniqueness is per
    # (platform, profile_id, account_id). sync_id = Turso cross-device id (IG rows only).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filtered_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            profile_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            filtered_at TEXT DEFAULT (datetime('now')),
            reason TEXT,
            source_type TEXT DEFAULT 'GENERAL',
            source_name TEXT DEFAULT 'unknown',
            session_id INTEGER,
            sync_id TEXT,
            UNIQUE(platform, profile_id, account_id)
        )
    """)

    # sessions removed (Vague B Phase C): folded into sessions_unified; dropped by run_migrations.

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile_stats_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            followers_count INTEGER NOT NULL,
            following_count INTEGER NOT NULL,
            posts_count INTEGER NOT NULL,
            engagement_rate REAL,
            is_verified INTEGER,
            biography TEXT,
            external_url TEXT,
            profile_pic_url TEXT,
            recorded_at TEXT DEFAULT (datetime('now'))
            -- profile_id FK to instagram_profiles dropped (Vague B: profiles unified; legacy is a view)
        )
    """)

    # instagram_posts removed (Vague B): dead table, never populated; dropped by run_migrations.

    # following_sync / followers_sync were folded into the unified
    # `social_graph_sync` table (Vague B) and are dropped by
    # run_social_graph_sync_migrations once their data is migrated. No longer
    # created here.


def create_instagram_indexes(cursor: sqlite3.Cursor) -> None:
    """Create Instagram core indexes."""
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_username ON instagram_accounts(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_filtered_account ON filtered_profiles(account_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_filtered_username ON filtered_profiles(username)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_filtered_profiles_sync_id ON filtered_profiles(sync_id)")
