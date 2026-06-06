"""Instagram migration steps."""

from __future__ import annotations

import sqlite3

from loguru import logger

from .identifiers import _validate_sql_identifier


def run_instagram_profile_core_migrations(cursor: sqlite3.Cursor) -> None:
    """Ensure instagram_profiles has the core post-release profile fields."""
    for col_name, col_def in [
        ("is_verified", "INTEGER DEFAULT 0"),
        ("is_business", "INTEGER DEFAULT 0"),
        ("business_category", "TEXT"),
        ("website", "TEXT"),
        ("linked_accounts", "TEXT"),
        ("account_based_in", "TEXT"),
        ("date_joined", "TEXT"),
        ("location_city", "TEXT"),
    ]:
        try:
            _col = _validate_sql_identifier(col_name)
            cursor.execute(f"SELECT {_col} FROM instagram_profiles LIMIT 1")
        except sqlite3.OperationalError:
            logger.info(f"Migration: Adding {col_name} to instagram_profiles")
            cursor.execute(f"ALTER TABLE instagram_profiles ADD COLUMN {_col} {col_def}")


def run_instagram_profile_ai_migrations(cursor: sqlite3.Cursor) -> None:
    """Ensure instagram_profiles has AI-derived classification fields."""
    try:
        cursor.execute("SELECT ai_gender FROM instagram_profiles LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding ai_gender to instagram_profiles")
        cursor.execute("ALTER TABLE instagram_profiles ADD COLUMN ai_gender TEXT")

    try:
        cursor.execute("SELECT ai_age_group FROM instagram_profiles LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding ai_age_group to instagram_profiles")
        cursor.execute("ALTER TABLE instagram_profiles ADD COLUMN ai_age_group TEXT")

    # Drop dead indexes on frozen ai_* columns: profile AI classification is read
    # from profile_ai_enrichments (runtime read cutoff), so these indexes served
    # no query and only slowed writes. Index hygiene only; no fact column change.
    for _idx in ("idx_instagram_profiles_ai_gender", "idx_instagram_profiles_ai_age_group"):
        try:
            cursor.execute(f"DROP INDEX IF EXISTS {_idx}")
        except sqlite3.OperationalError:
            pass
