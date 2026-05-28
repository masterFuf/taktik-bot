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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interaction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            account_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL,
            interaction_type TEXT NOT NULL,
            interaction_time TEXT DEFAULT (datetime('now')),
            success INTEGER DEFAULT 1,
            content TEXT,
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
            FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filtered_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            filtered_at TEXT DEFAULT (datetime('now')),
            reason TEXT,
            source_type TEXT DEFAULT 'GENERAL',
            source_name TEXT DEFAULT 'unknown',
            session_id INTEGER,
            FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
            UNIQUE(profile_id, account_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            session_name TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target TEXT NOT NULL,
            start_time TEXT DEFAULT (datetime('now')),
            end_time TEXT,
            duration_seconds INTEGER DEFAULT 0,
            config_used TEXT,
            status TEXT DEFAULT 'ACTIVE',
            error_message TEXT,
            synced_to_api INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE
        )
    """)

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
            recorded_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS instagram_posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            account_id INTEGER,
            source TEXT DEFAULT 'SCRAPED',
            instagram_post_id TEXT UNIQUE,
            instagram_id TEXT,
            media_type TEXT NOT NULL,
            is_video INTEGER DEFAULT 0,
            caption TEXT,
            media_urls TEXT,
            thumbnail_url TEXT,
            video_url TEXT,
            likes_count INTEGER DEFAULT 0,
            comments_count INTEGER DEFAULT 0,
            views_count INTEGER DEFAULT 0,
            posted_at TEXT,
            scraped_at TEXT,
            hashtags TEXT,
            mentions TEXT,
            tagged_users TEXT,
            location TEXT,
            location_data TEXT,
            coauthors TEXT,
            status TEXT DEFAULT 'DRAFT',
            scheduled_for TEXT,
            published_at TEXT,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            dimensions TEXT,
            product_type TEXT,
            accessibility_caption TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            total_likes INTEGER DEFAULT 0,
            total_follows INTEGER DEFAULT 0,
            total_unfollows INTEGER DEFAULT 0,
            total_comments INTEGER DEFAULT 0,
            total_story_views INTEGER DEFAULT 0,
            total_story_likes INTEGER DEFAULT 0,
            total_profile_visits INTEGER DEFAULT 0,
            total_sessions INTEGER DEFAULT 0,
            completed_sessions INTEGER DEFAULT 0,
            failed_sessions INTEGER DEFAULT 0,
            total_duration_seconds INTEGER DEFAULT 0,
            synced_to_api INTEGER DEFAULT 0,
            synced_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
            UNIQUE(account_id, date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS following_sync (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            first_seen_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now')),
            is_follower_back INTEGER DEFAULT NULL,
            followed_by_bot INTEGER DEFAULT 0,
            unfollowed_at TEXT DEFAULT NULL,
            source TEXT DEFAULT 'sync',
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
            UNIQUE(account_id, username)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS followers_sync (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            first_seen_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now')),
            is_following_back INTEGER DEFAULT NULL,
            source TEXT DEFAULT 'sync',
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
            UNIQUE(account_id, username)
        )
    """)


def create_instagram_indexes(cursor: sqlite3.Cursor) -> None:
    """Create Instagram core indexes."""
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_username ON instagram_accounts(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_username ON instagram_profiles(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_session ON interaction_history(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_account ON interaction_history(account_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_time ON interaction_history(interaction_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_filtered_account ON filtered_profiles(account_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_filtered_username ON filtered_profiles(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_stats_account_date ON daily_stats(account_id, date)")
