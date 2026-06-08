"""Instagram scraping migration steps."""

from __future__ import annotations

import sqlite3

from loguru import logger

from .identifiers import _validate_sql_identifier


def drop_scraped_comments(cursor: sqlite3.Cursor) -> None:
    """Vague F1: drop the dead ``scraped_comments`` table.

    Confirmed dead before removal: no live writer/reader (the
    ``save_scraped_comment`` + getters were orphaned, 0 callers), 405 rows with
    100% NULL ``content``, last write 2026-01-17 — superseded by
    ``smart_comment_replies``. Backup exported to
    ``%APPDATA%/taktik-desktop/backups/scraped_comments_backup_2026-06-08.csv``.
    No FK child references it (it FK'd scraping_sessions), so the drop is safe.
    Idempotent; the CREATE has been removed from the schema bootstrap so it does
    not come back.
    """
    cursor.execute("DROP TABLE IF EXISTS scraped_comments")


def run_scraping_session_migrations(cursor: sqlite3.Cursor) -> None:
    """Ensure scraping_sessions has platform fields."""
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
