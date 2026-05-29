"""TikTok migration steps."""

from __future__ import annotations

import sqlite3

from loguru import logger


def run_legacy_tiktok_scraped_profiles_migration(cursor: sqlite3.Cursor) -> None:
    """Convert old tiktok_scraped_profiles profile snapshots to a junction table."""
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tiktok_scraped_profiles'")
        if not cursor.fetchone():
            return

        cursor.execute("PRAGMA table_info(tiktok_scraped_profiles)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'bio' not in columns or 'followers_count' not in columns:
            return

        logger.info("Migration: Migrating old tiktok_scraped_profiles data to tiktok_profiles")
        cursor.execute("""
            INSERT OR IGNORE INTO tiktok_profiles
                (username, display_name, followers_count, following_count, likes_count,
                 videos_count, biography, is_private, is_verified)
            SELECT DISTINCT
                username, display_name, followers_count, following_count, likes_count,
                posts_count, bio, is_private, is_verified
            FROM tiktok_scraped_profiles
            WHERE username IS NOT NULL AND username != ''
        """)
        migrated = cursor.rowcount
        if migrated > 0:
            logger.info(f"Migration: Migrated {migrated} TikTok profiles to main table")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _tiktok_scraped_profiles_backup AS
            SELECT scraping_id, username, is_enriched, scraped_at
            FROM tiktok_scraped_profiles
        """)
        cursor.execute("DROP TABLE IF EXISTS tiktok_scraped_profiles")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tiktok_scraped_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraping_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                is_enriched INTEGER DEFAULT 0,
                scraped_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (scraping_id) REFERENCES scraping_sessions(scraping_id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES tiktok_profiles(profile_id) ON DELETE CASCADE,
                UNIQUE(scraping_id, profile_id)
            )
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO tiktok_scraped_profiles (scraping_id, profile_id, is_enriched, scraped_at)
            SELECT b.scraping_id, tp.profile_id, b.is_enriched, b.scraped_at
            FROM _tiktok_scraped_profiles_backup b
            JOIN tiktok_profiles tp ON tp.username = b.username
            WHERE b.scraping_id IS NOT NULL
        """)
        cursor.execute("DROP TABLE IF EXISTS _tiktok_scraped_profiles_backup")
        logger.info("Migration: TikTok scraped profiles table converted to junction table")
    except sqlite3.OperationalError as e:
        logger.warning(f"Migration warning (tiktok_scraped_profiles): {e}")
