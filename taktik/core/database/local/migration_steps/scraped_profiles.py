"""Unified scraped_profiles table migration (Vague B, platform axis).

Folds ``tiktok_scraped_profiles`` into ``scraped_profiles`` via a ``platform``
column. ``scraping_sessions`` is already unified (platform-keyed), so
``scraping_id`` is globally unique and platform-bound; the ``platform`` column
disambiguates the polymorphic ``profile_id``. The Instagram table is rebuilt in
place when it predates the column (add ``platform`` + ``is_enriched``, drop the
cross-table foreign keys), preserving every ``id``; the TikTok junction rows are
backfilled (``platform='tiktok'``, carrying ``is_enriched``), then the legacy
twin is dropped. Not Turso-synced (no ``sync_id``). Idempotent: the rebuild only
runs while ``platform`` is still missing.

Must run after ``run_legacy_tiktok_scraped_profiles_migration`` (which converts
the very old profile-snapshot shape into the junction shape) and after
``run_scraped_profile_migrations`` (which adds the AI / source_post_url columns).
"""

from __future__ import annotations

import sqlite3

from loguru import logger


def run_scraped_profiles_unification_migrations(cursor: sqlite3.Cursor) -> None:
    cols = [row[1] for row in cursor.execute("PRAGMA table_info(scraped_profiles)").fetchall()]

    if cols and "platform" not in cols:
        cursor.execute(
            """
            CREATE TABLE scraped_profiles_new (
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
            """
        )
        has_source = "source_post_url" in cols
        source_expr = "source_post_url" if has_source else "NULL"
        cursor.execute(
            f"""
            INSERT INTO scraped_profiles_new
                (id, platform, scraping_id, profile_id, scraped_at, is_enriched,
                 source_post_url, ai_score, ai_qualified, ai_analysis, qualification_criteria, scored_at)
            SELECT id, 'instagram', scraping_id, profile_id, scraped_at, 0,
                   {source_expr}, ai_score, ai_qualified, ai_analysis, qualification_criteria, scored_at
            FROM scraped_profiles
            """
        )
        cursor.execute("DROP TABLE scraped_profiles")
        cursor.execute("ALTER TABLE scraped_profiles_new RENAME TO scraped_profiles")
        logger.info("Rebuilt scraped_profiles with platform axis")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_session ON scraped_profiles(scraping_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_profile ON scraped_profiles(profile_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_qualified ON scraped_profiles(ai_qualified)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_score ON scraped_profiles(ai_score)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_scraped_profiles_post_url ON scraped_profiles(source_post_url) "
        "WHERE source_post_url IS NOT NULL"
    )

    # Backfill TikTok junction rows (platform='tiktok'), then drop the twin.
    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO scraped_profiles
                (platform, scraping_id, profile_id, scraped_at, is_enriched)
            SELECT 'tiktok', scraping_id, profile_id, scraped_at, is_enriched
            FROM tiktok_scraped_profiles
            """
        )
    except sqlite3.OperationalError as exc:
        logger.debug(f"scraped_profiles tiktok backfill skipped: {exc}")
    cursor.execute("DROP TABLE IF EXISTS tiktok_scraped_profiles")
