"""Instagram scraping schema definitions."""

from __future__ import annotations

import sqlite3


def create_scraping_tables(cursor: sqlite3.Cursor) -> None:
    """Create scraping tables."""
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
            platform TEXT DEFAULT 'instagram',
            created_at TEXT DEFAULT (datetime('now'))
            -- account_id FK to instagram_accounts dropped (Vague B: accounts unified/legacy dropped)
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
            UNIQUE(account_id, hashtag, post_author, post_caption_hash)
        )
    """)

    cursor.execute("""
        -- Unified scraped_profiles (platform axis: instagram + tiktok). scraping_id is
        -- globally unique (shared scraping_sessions) so it is platform-bound; the
        -- `platform` column disambiguates the polymorphic profile_id. No cross-table FK.
        CREATE TABLE IF NOT EXISTS scraped_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            scraping_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL,
            scraped_at TEXT DEFAULT (datetime('now')),
            is_enriched INTEGER DEFAULT 0,
            source_post_url TEXT,
            ai_score INTEGER,
            ai_qualified INTEGER DEFAULT 0,
            ai_analysis TEXT,
            qualification_criteria TEXT,
            scored_at TEXT,
            UNIQUE(scraping_id, profile_id)
        )
    """)

    # scraped_comments removed (Vague F1): dead table (no live writer/reader, 100%
    # NULL content, superseded by smart_comment_replies). Dropped in migrations
    # (drop_scraped_comments) and no longer created here.


def create_scraping_indexes(cursor: sqlite3.Cursor) -> None:
    """Create scraping indexes."""
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraping_sessions_status ON scraping_sessions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraping_sessions_source ON scraping_sessions(source_type, source_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processed_hashtag_posts_lookup ON processed_hashtag_posts(account_id, hashtag, post_author)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_session ON scraped_profiles(scraping_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_profile ON scraped_profiles(profile_id)")
