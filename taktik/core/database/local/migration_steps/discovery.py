"""Discovery and scraping migration steps."""

from __future__ import annotations

import sqlite3

from loguru import logger

from .identifiers import _validate_sql_identifier


def run_scraped_comments_migrations(cursor: sqlite3.Cursor) -> None:
    """Ensure scraped_comments has the post-release columns and indexes."""
    try:
        cursor.execute("SELECT scraping_session_id FROM scraped_comments LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding scraping_session_id to scraped_comments")
        cursor.execute("ALTER TABLE scraped_comments ADD COLUMN scraping_session_id INTEGER")

    try:
        cursor.execute("SELECT profile_id FROM scraped_comments LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding profile_id to scraped_comments")
        cursor.execute("ALTER TABLE scraped_comments ADD COLUMN profile_id INTEGER")

    try:
        cursor.execute("SELECT target_username FROM scraped_comments LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding target_username to scraped_comments")
        cursor.execute("ALTER TABLE scraped_comments ADD COLUMN target_username TEXT")

    try:
        cursor.execute("SELECT is_reply FROM scraped_comments LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding is_reply to scraped_comments")
        cursor.execute("ALTER TABLE scraped_comments ADD COLUMN is_reply INTEGER DEFAULT 0")

    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_comments_session ON scraped_comments(scraping_session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_comments_username ON scraped_comments(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_comments_target ON scraped_comments(target_username)")
    except sqlite3.OperationalError:
        pass


def run_scraping_session_migrations(cursor: sqlite3.Cursor) -> None:
    """Ensure scraping_sessions has discovery and platform fields."""
    try:
        cursor.execute("SELECT discovery_campaign_id FROM scraping_sessions LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding discovery_campaign_id to scraping_sessions")
        cursor.execute("ALTER TABLE scraping_sessions ADD COLUMN discovery_campaign_id INTEGER")

    try:
        cursor.execute("SELECT platform FROM scraping_sessions LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding platform to scraping_sessions")
        cursor.execute("ALTER TABLE scraping_sessions ADD COLUMN platform TEXT DEFAULT 'instagram'")


def run_scraped_profile_migrations(cursor: sqlite3.Cursor) -> None:
    """Ensure scraped_profiles has AI qualification and source post fields."""
    for col_name, col_def in [
        ("ai_score", "INTEGER"),
        ("ai_qualified", "INTEGER DEFAULT 0"),
        ("ai_analysis", "TEXT"),
        ("qualification_criteria", "TEXT"),
        ("scored_at", "TEXT"),
    ]:
        try:
            _col = _validate_sql_identifier(col_name)
            cursor.execute(f"SELECT {_col} FROM scraped_profiles LIMIT 1")
        except sqlite3.OperationalError:
            logger.info(f"Migration: Adding {col_name} to scraped_profiles")
            cursor.execute(f"ALTER TABLE scraped_profiles ADD COLUMN {_col} {col_def}")

    try:
        cursor.execute("SELECT source_post_url FROM scraped_profiles LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding source_post_url to scraped_profiles")
        cursor.execute("ALTER TABLE scraped_profiles ADD COLUMN source_post_url TEXT")

    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_qualified ON scraped_profiles(ai_qualified)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_score ON scraped_profiles(ai_score)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_post_url ON scraped_profiles(source_post_url)")
    except sqlite3.OperationalError:
        pass
