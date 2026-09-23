"""Instagram migration steps."""

from __future__ import annotations

import sqlite3

from loguru import logger

from .identifiers import _validate_sql_identifier


def _ensure_instagram_profile_column(cursor: sqlite3.Cursor, col_name: str, col_def: str) -> None:
    """Add a column to `instagram_profiles` when it is missing, and only when it can be added.

    `instagram_profiles` is a VIEW over `social_profiles` in the unified databases, and SQLite
    cannot add a column to a view. The column-add used to sit, unprotected, in the `except` of
    the probing SELECT: the day the view lacked one of these columns, the error went up to
    `LocalDatabaseService.__init__` and the bot could no longer open its database (2026-09-23).
    Now: the column is looked up (`PRAGMA table_info` reads views too), a view or a missing object
    is left alone, and any database error on the way is logged, never raised.

    A column missing from the VIEW is a developer's error, not a state to repair here: it must be
    added to `social_profiles` in both runtimes and the view recreated (DROP then CREATE) on both
    sides (`social_profiles.py`, `electron/database/migrations.ts`). It is logged as an error at
    each start, so it does not go unnoticed until a query fails.
    """
    col = _validate_sql_identifier(col_name)
    try:
        columns = {row[1] for row in cursor.execute("PRAGMA table_info(instagram_profiles)").fetchall()}
        if col in columns:
            return
        row = cursor.execute("SELECT type FROM sqlite_master WHERE name = 'instagram_profiles'").fetchone()
        kind = row[0] if row else None
        if kind == "view":
            logger.error(
                f"Migration: the instagram_profiles view has no {col_name}: add it to social_profiles "
                "in both runtimes and recreate the view on both sides (a view takes no column)"
            )
            return
        if kind != "table":
            logger.warning(f"Migration: instagram_profiles is missing, {col_name} not added")
            return
        logger.info(f"Migration: Adding {col_name} to instagram_profiles")
        cursor.execute(f"ALTER TABLE instagram_profiles ADD COLUMN {col} {col_def}")
    except sqlite3.Error as exc:
        # A locked base, a broken view: the column waits for the next start, the base opens.
        logger.warning(f"Migration: could not check or add {col_name} on instagram_profiles: {exc}")


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
        _ensure_instagram_profile_column(cursor, col_name, col_def)


def run_instagram_profile_ai_migrations(cursor: sqlite3.Cursor) -> None:
    """Ensure instagram_profiles has AI-derived classification fields."""
    _ensure_instagram_profile_column(cursor, "ai_gender", "TEXT")
    _ensure_instagram_profile_column(cursor, "ai_age_group", "TEXT")

    # Drop dead indexes on frozen ai_* columns: profile AI classification is read
    # from profile_ai_enrichments (runtime read cutoff), so these indexes served
    # no query and only slowed writes. Index hygiene only; no fact column change.
    for _idx in ("idx_instagram_profiles_ai_gender", "idx_instagram_profiles_ai_age_group"):
        try:
            cursor.execute(f"DROP INDEX IF EXISTS {_idx}")
        except sqlite3.OperationalError:
            pass
