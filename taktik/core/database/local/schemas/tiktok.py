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


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tiktok_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            session_name TEXT NOT NULL,
            workflow_type TEXT NOT NULL,
            target TEXT,
            start_time TEXT DEFAULT (datetime('now')),
            end_time TEXT,
            duration_seconds INTEGER DEFAULT 0,
            config_used TEXT,
            status TEXT DEFAULT 'ACTIVE',
            profiles_visited INTEGER DEFAULT 0,
            posts_watched INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            follows INTEGER DEFAULT 0,
            favorites INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES tiktok_accounts(account_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tiktok_filtered_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            filtered_at TEXT DEFAULT (datetime('now')),
            reason TEXT,
            source_type TEXT DEFAULT 'GENERAL',
            source_name TEXT DEFAULT 'unknown',
            session_id INTEGER,
            FOREIGN KEY (profile_id) REFERENCES tiktok_profiles(profile_id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES tiktok_accounts(account_id) ON DELETE CASCADE,
            UNIQUE(profile_id, account_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tiktok_daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            total_likes INTEGER DEFAULT 0,
            total_follows INTEGER DEFAULT 0,
            total_favorites INTEGER DEFAULT 0,
            total_comments INTEGER DEFAULT 0,
            total_shares INTEGER DEFAULT 0,
            total_profile_visits INTEGER DEFAULT 0,
            total_posts_watched INTEGER DEFAULT 0,
            total_sessions INTEGER DEFAULT 0,
            completed_sessions INTEGER DEFAULT 0,
            failed_sessions INTEGER DEFAULT 0,
            total_duration_seconds INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES tiktok_accounts(account_id) ON DELETE CASCADE,
            UNIQUE(account_id, date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tiktok_scraped_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scraping_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL,
            is_enriched INTEGER DEFAULT 0,
            scraped_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (profile_id) REFERENCES tiktok_profiles(profile_id) ON DELETE CASCADE,
            UNIQUE(scraping_id, profile_id)
        )
    """)


def create_tiktok_indexes(cursor: sqlite3.Cursor) -> None:
    """Create TikTok indexes."""
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_accounts_username ON tiktok_accounts(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_profiles_username ON tiktok_profiles(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_sessions_account ON tiktok_sessions(account_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_sessions_status ON tiktok_sessions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_filtered_account ON tiktok_filtered_profiles(account_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_filtered_username ON tiktok_filtered_profiles(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_daily_stats_account_date ON tiktok_daily_stats(account_id, date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_scraped_profiles_session ON tiktok_scraped_profiles(scraping_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_scraped_profiles_profile ON tiktok_scraped_profiles(profile_id)")
