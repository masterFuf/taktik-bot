"""Cross-platform enrichment schema definitions."""

from __future__ import annotations

import sqlite3


def create_enrichment_tables(cursor: sqlite3.Cursor) -> None:
    """Create tables for derived/enriched profile data."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile_ai_enrichments (
            enrichment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            profile_id INTEGER,
            username TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'legacy',
            model TEXT NOT NULL DEFAULT 'legacy',
            criteria_hash TEXT NOT NULL DEFAULT 'legacy_profile_ai',
            ai_niche TEXT,
            ai_specific_niche TEXT,
            ai_score INTEGER,
            ai_classification TEXT,
            ai_profession TEXT,
            ai_profession_tags TEXT,
            ai_gender TEXT,
            ai_age_group TEXT,
            ai_account_based_in TEXT,
            location_city TEXT,
            location_region TEXT,
            analysis_json TEXT,
            source TEXT NOT NULL DEFAULT 'ai',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(platform, username, criteria_hash, provider, model)
        )
    """)


def create_enrichment_indexes(cursor: sqlite3.Cursor) -> None:
    """Create indexes for enrichment lookups."""
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_profile_ai_enrichments_lookup "
        "ON profile_ai_enrichments(platform, username)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_profile_ai_enrichments_profile "
        "ON profile_ai_enrichments(platform, profile_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_profile_ai_enrichments_score "
        "ON profile_ai_enrichments(platform, ai_score)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_profile_ai_enrichments_updated "
        "ON profile_ai_enrichments(updated_at)"
    )
