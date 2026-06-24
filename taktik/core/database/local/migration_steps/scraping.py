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


def drop_scraping_sessions_discovery_campaign_id(cursor: sqlite3.Cursor) -> None:
    """Lot 4 (audit 2026-06-08): drop the dead ``scraping_sessions.discovery_campaign_id``.

    The referent tables (``discovery_campaigns`` / ``discovered_profiles``) were already
    dropped (Vague A/B), so this is a dangling FK column with no referent and **0 runtime
    read/write** (only the front de-FK rebuild ever referenced it). On the live DB it is
    100% NULL across 262 rows. SQLite (this version) has no ``DROP COLUMN``, and an index
    targets the column, so rebuild the table without it.

    Idempotent: no-op once the column is gone (fresh installs never had it — the schema
    bootstrap CREATE does not declare it). Validated byte-for-byte on a copy of the real
    DB (262 rows preserved, kept-column hash identical, FK check clean) before shipping.
    See ``internal docs`` (section F-cleanup).
    """
    cols = [row[1] for row in cursor.execute("PRAGMA table_info(scraping_sessions)").fetchall()]
    if not cols or "discovery_campaign_id" not in cols:
        return  # fresh install / already cleaned

    keep = [col for col in cols if col != "discovery_campaign_id"]
    keep_csv = ", ".join(keep)

    logger.info("Migration: rebuilding scraping_sessions without dead discovery_campaign_id")
    cursor.execute("DROP INDEX IF EXISTS idx_scraping_sessions_discovery")
    cursor.execute("DROP TABLE IF EXISTS scraping_sessions_new")
    cursor.execute("""
        CREATE TABLE scraping_sessions_new (
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
            created_at TEXT DEFAULT (datetime('now')),
            sync_id TEXT
        )
    """)
    cursor.execute(
        f"INSERT INTO scraping_sessions_new ({keep_csv}) "
        f"SELECT {keep_csv} FROM scraping_sessions"
    )
    cursor.execute("DROP TABLE scraping_sessions")
    cursor.execute("ALTER TABLE scraping_sessions_new RENAME TO scraping_sessions")
    # Recreate the surviving indexes (the discovery index is intentionally not recreated).
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraping_sessions_status ON scraping_sessions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraping_sessions_source ON scraping_sessions(source_type, source_name)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_scraping_sessions_sync_id ON scraping_sessions(sync_id)")


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
