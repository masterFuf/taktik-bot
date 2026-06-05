"""Migration steps for cross-platform profile enrichments."""

from __future__ import annotations

import sqlite3
from typing import Iterable


LEGACY_PROFILE_AI_COLUMNS = (
    "ai_niche",
    "ai_specific_niche",
    "ai_score",
    "ai_classification",
    "ai_profession",
    "ai_profession_tags",
    "ai_gender",
    "ai_age_group",
    "account_based_in",
    "location_city",
    "location_region",
)


def _table_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row[1] for row in cursor.fetchall()}
    except sqlite3.Error:
        return set()


def _column_expr(columns: set[str], column_name: str) -> str:
    return f"ip.{column_name}" if column_name in columns else "NULL"


def _non_empty_predicates(columns: Iterable[str]) -> list[str]:
    predicates = []
    for column in columns:
        if column == "ai_score":
            predicates.append(f"ip.{column} IS NOT NULL")
        else:
            predicates.append(
                f"(ip.{column} IS NOT NULL AND trim(CAST(ip.{column} AS TEXT)) != '')"
            )
    return predicates


def run_profile_ai_enrichment_migrations(cursor: sqlite3.Cursor) -> None:
    """Create profile_ai_enrichments and backfill legacy Instagram AI columns."""
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

    profile_columns = _table_columns(cursor, "instagram_profiles")
    if not profile_columns:
        return

    existing_ai_columns = [
        column for column in LEGACY_PROFILE_AI_COLUMNS if column in profile_columns
    ]
    predicates = _non_empty_predicates(existing_ai_columns)
    if not predicates:
        return

    cursor.execute(f"""
        INSERT INTO profile_ai_enrichments (
            platform, profile_id, username, provider, model, criteria_hash,
            ai_niche, ai_specific_niche, ai_score, ai_classification,
            ai_profession, ai_profession_tags, ai_gender, ai_age_group,
            ai_account_based_in, location_city, location_region, source,
            created_at, updated_at
        )
        SELECT
            'instagram',
            ip.profile_id,
            ip.username,
            'legacy',
            'legacy',
            'legacy_profile_ai',
            {_column_expr(profile_columns, "ai_niche")},
            {_column_expr(profile_columns, "ai_specific_niche")},
            {_column_expr(profile_columns, "ai_score")},
            {_column_expr(profile_columns, "ai_classification")},
            {_column_expr(profile_columns, "ai_profession")},
            {_column_expr(profile_columns, "ai_profession_tags")},
            {_column_expr(profile_columns, "ai_gender")},
            {_column_expr(profile_columns, "ai_age_group")},
            {_column_expr(profile_columns, "account_based_in")},
            {_column_expr(profile_columns, "location_city")},
            {_column_expr(profile_columns, "location_region")},
            'legacy_backfill',
            COALESCE({_column_expr(profile_columns, "created_at")}, datetime('now')),
            COALESCE({_column_expr(profile_columns, "ai_classified_at")}, {_column_expr(profile_columns, "updated_at")}, datetime('now'))
        FROM instagram_profiles ip
        WHERE ip.username IS NOT NULL
          AND trim(ip.username) != ''
          AND ({" OR ".join(predicates)})
        ON CONFLICT(platform, username, criteria_hash, provider, model) DO UPDATE SET
            profile_id = COALESCE(excluded.profile_id, profile_ai_enrichments.profile_id),
            ai_niche = COALESCE(excluded.ai_niche, profile_ai_enrichments.ai_niche),
            ai_specific_niche = COALESCE(excluded.ai_specific_niche, profile_ai_enrichments.ai_specific_niche),
            ai_score = COALESCE(excluded.ai_score, profile_ai_enrichments.ai_score),
            ai_classification = COALESCE(excluded.ai_classification, profile_ai_enrichments.ai_classification),
            ai_profession = COALESCE(excluded.ai_profession, profile_ai_enrichments.ai_profession),
            ai_profession_tags = COALESCE(excluded.ai_profession_tags, profile_ai_enrichments.ai_profession_tags),
            ai_gender = COALESCE(excluded.ai_gender, profile_ai_enrichments.ai_gender),
            ai_age_group = COALESCE(excluded.ai_age_group, profile_ai_enrichments.ai_age_group),
            ai_account_based_in = COALESCE(excluded.ai_account_based_in, profile_ai_enrichments.ai_account_based_in),
            location_city = COALESCE(excluded.location_city, profile_ai_enrichments.location_city),
            location_region = COALESCE(excluded.location_region, profile_ai_enrichments.location_region),
            source = excluded.source,
            updated_at = excluded.updated_at
    """)
