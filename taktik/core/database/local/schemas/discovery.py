"""Discovery and scraping schema definitions."""

from __future__ import annotations

import sqlite3


def create_discovery_tables(cursor: sqlite3.Cursor) -> None:
    """Create discovery and scraping tables."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scraping_sessions (
            scraping_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            scraping_type TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_name TEXT NOT NULL,
            total_scraped INTEGER DEFAULT 0,
            max_profiles INTEGER DEFAULT 500,
            export_csv INTEGER DEFAULT 0,
            csv_path TEXT,
            save_to_db INTEGER DEFAULT 1,
            start_time TEXT DEFAULT (datetime('now')),
            end_time TEXT,
            duration_seconds INTEGER DEFAULT 0,
            status TEXT DEFAULT 'RUNNING',
            error_message TEXT,
            config_used TEXT,
            discovery_campaign_id INTEGER,
            platform TEXT DEFAULT 'instagram',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE SET NULL,
            FOREIGN KEY (discovery_campaign_id) REFERENCES discovery_campaigns(campaign_id) ON DELETE SET NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_hashtag_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            hashtag TEXT NOT NULL,
            post_author TEXT NOT NULL,
            post_caption_hash TEXT,
            post_caption_preview TEXT,
            likes_count INTEGER,
            comments_count INTEGER,
            likers_processed INTEGER DEFAULT 0,
            interactions_made INTEGER DEFAULT 0,
            processed_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
            UNIQUE(account_id, hashtag, post_author, post_caption_hash)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS discovery_campaigns (
            campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            name TEXT NOT NULL,
            niche_keywords TEXT DEFAULT '[]',
            target_hashtags TEXT DEFAULT '[]',
            target_accounts TEXT DEFAULT '[]',
            target_post_urls TEXT DEFAULT '[]',
            total_discovered INTEGER DEFAULT 0,
            total_qualified INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ACTIVE',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE SET NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS discovery_progress (
            progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            source_value TEXT NOT NULL,
            current_post_index INTEGER DEFAULT 0,
            total_posts INTEGER DEFAULT 0,
            current_phase TEXT DEFAULT 'profile',
            likers_scraped INTEGER DEFAULT 0,
            likers_total INTEGER DEFAULT 0,
            comments_scraped INTEGER DEFAULT 0,
            comments_total INTEGER DEFAULT 0,
            last_scroll_position TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (campaign_id) REFERENCES discovery_campaigns(campaign_id) ON DELETE CASCADE,
            UNIQUE(campaign_id, source_type, source_value)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS discovered_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            source_type TEXT,
            source_name TEXT,
            biography TEXT,
            followers_count INTEGER DEFAULT 0,
            following_count INTEGER DEFAULT 0,
            posts_count INTEGER DEFAULT 0,
            is_private INTEGER DEFAULT 0,
            is_verified INTEGER DEFAULT 0,
            is_business INTEGER DEFAULT 0,
            category TEXT,
            engagement_score REAL,
            ai_score REAL,
            status TEXT DEFAULT 'new',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (campaign_id) REFERENCES discovery_campaigns(campaign_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scraped_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scraping_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL,
            scraped_at TEXT DEFAULT (datetime('now')),
            source_post_url TEXT,
            ai_score INTEGER,
            ai_qualified INTEGER DEFAULT 0,
            ai_analysis TEXT,
            qualification_criteria TEXT,
            scored_at TEXT,
            FOREIGN KEY (scraping_id) REFERENCES scraping_sessions(scraping_id) ON DELETE CASCADE,
            FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id) ON DELETE CASCADE,
            UNIQUE(scraping_id, profile_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scraped_comments (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scraping_session_id INTEGER,
            profile_id INTEGER,
            target_username TEXT,
            post_url TEXT,
            username TEXT NOT NULL,
            content TEXT,
            likes_count INTEGER DEFAULT 0,
            is_reply INTEGER DEFAULT 0,
            parent_comment_id INTEGER,
            scraped_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (scraping_session_id) REFERENCES scraping_sessions(scraping_id) ON DELETE SET NULL,
            FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id) ON DELETE SET NULL
        )
    """)


def create_discovery_indexes(cursor: sqlite3.Cursor) -> None:
    """Create discovery and scraping indexes."""
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraping_sessions_status ON scraping_sessions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraping_sessions_source ON scraping_sessions(source_type, source_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processed_hashtag_posts_lookup ON processed_hashtag_posts(account_id, hashtag, post_author)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_session ON scraped_profiles(scraping_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_profile ON scraped_profiles(profile_id)")
