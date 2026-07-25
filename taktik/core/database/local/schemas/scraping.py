"""Instagram scraping schema definitions."""

from __future__ import annotations

import sqlite3


def scraping_sessions_ddl(table_name: str = "scraping_sessions", if_not_exists: bool = True) -> str:
    """The one definition of ``scraping_sessions``, usable under another name.

    The table-rebuild migration needs the same shape under a temporary name, and used to restate
    the whole CREATE by hand. The two copies had already drifted — ``created_at`` and ``sync_id``
    were declared in opposite order — which is harmless in SQLite but is the first step of a base
    that differs depending on whether it was created or migrated.

    ``table_name`` is interpolated, so it must never come from outside this module.
    """
    guard = "IF NOT EXISTS " if if_not_exists else ""
    return f"""
        CREATE TABLE {guard}{table_name} (
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
            sync_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
            -- account_id FK to instagram_accounts dropped (Vague B: accounts unified/legacy dropped)
            -- sync_id = stable cross-device key (Turso); NULL until assigned at row creation.
        )
    """


def create_scraping_tables(cursor: sqlite3.Cursor) -> None:
    """Create scraping tables."""
    cursor.execute(scraping_sessions_ddl())

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
    # `WHERE scraping_type = ? ORDER BY start_time DESC` is issued by both the bot and the
    # desktop; without this it is a full scan plus a temp B-tree for the sort (confirmed with
    # EXPLAIN QUERY PLAN on the real base). The sort column is part of the index so the ORDER BY
    # is satisfied by the walk itself.
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraping_sessions_type ON scraping_sessions(scraping_type, start_time DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processed_hashtag_posts_lookup ON processed_hashtag_posts(account_id, hashtag, post_author)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_session ON scraped_profiles(scraping_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_profile ON scraped_profiles(profile_id)")
