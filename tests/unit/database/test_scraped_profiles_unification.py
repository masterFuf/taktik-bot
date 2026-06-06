"""Unit tests for the unified `scraped_profiles` table (Vague B, platform axis)."""

import sqlite3

from taktik.core.database.local.migration_steps.scraped_profiles import (
    run_scraped_profiles_unification_migrations,
)


def _legacy_base() -> sqlite3.Connection:
    """A raw connection mimicking an old base: pre-platform scraped_profiles +
    the legacy tiktok_scraped_profiles junction twin."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE scraped_profiles (
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
            UNIQUE(scraping_id, profile_id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE tiktok_scraped_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scraping_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL,
            is_enriched INTEGER DEFAULT 0,
            scraped_at TEXT DEFAULT (datetime('now')),
            UNIQUE(scraping_id, profile_id)
        )
        """
    )
    con.execute(
        "INSERT INTO scraped_profiles (scraping_id, profile_id, ai_score, ai_qualified, source_post_url) "
        "VALUES (1, 100, 85, 1, 'https://example.com/p/abc')"
    )
    con.execute(
        "INSERT INTO tiktok_scraped_profiles (scraping_id, profile_id, is_enriched) VALUES (2, 200, 1)"
    )
    con.commit()
    return con


def test_fold_tiktok_and_preserve_instagram():
    con = _legacy_base()
    run_scraped_profiles_unification_migrations(con.cursor())

    cols = [r[1] for r in con.execute("PRAGMA table_info(scraped_profiles)").fetchall()]
    assert "platform" in cols
    assert "is_enriched" in cols

    ig = con.execute(
        "SELECT id, ai_score, ai_qualified, source_post_url FROM scraped_profiles "
        "WHERE platform = 'instagram' AND scraping_id = 1 AND profile_id = 100"
    ).fetchone()
    assert ig is not None
    assert ig["id"] == 1                      # id preserved
    assert ig["ai_score"] == 85               # AI scoring preserved
    assert ig["ai_qualified"] == 1
    assert ig["source_post_url"] == "https://example.com/p/abc"

    tt = con.execute(
        "SELECT is_enriched FROM scraped_profiles WHERE platform = 'tiktok' AND scraping_id = 2 AND profile_id = 200"
    ).fetchone()
    assert tt is not None
    assert tt["is_enriched"] == 1             # TikTok enrichment flag carried

    dropped = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tiktok_scraped_profiles'"
    ).fetchone()
    assert dropped is None
    con.close()


def test_unification_is_idempotent():
    con = _legacy_base()
    run_scraped_profiles_unification_migrations(con.cursor())
    run_scraped_profiles_unification_migrations(con.cursor())  # no-op second run

    total = con.execute("SELECT COUNT(*) AS c FROM scraped_profiles").fetchone()["c"]
    assert total == 2  # 1 IG + 1 TikTok, no duplication
    con.close()
