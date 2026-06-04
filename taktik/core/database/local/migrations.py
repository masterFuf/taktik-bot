"""Migration orchestration for the TAKTIK local SQLite database.

The public API stays here because callers import ``run_migrations`` and
``_validate_sql_identifier`` from this module. Domain-specific migration steps
live under ``local/migration_steps``.
"""

from __future__ import annotations

import sqlite3

from .migration_steps.scraping import (
    run_scraped_comments_migrations,
    run_scraped_profile_migrations,
    run_scraping_session_migrations,
)
from .migration_steps.identifiers import _validate_sql_identifier
from .migration_steps.instagram import (
    run_instagram_profile_ai_migrations,
    run_instagram_profile_core_migrations,
)
from .migration_steps.social_graph import run_profile_following_migrations
from .migration_steps.tiktok import run_legacy_tiktok_scraped_profiles_migration


def run_migrations(conn: sqlite3.Connection) -> None:
    """Run idempotent migrations against an existing local SQLite database."""
    cursor = conn.cursor()

    # Keep the historical order to avoid subtle regressions on old databases.
    run_scraped_comments_migrations(cursor)
    run_instagram_profile_core_migrations(cursor)
    run_scraping_session_migrations(cursor)
    run_scraped_profile_migrations(cursor)
    run_legacy_tiktok_scraped_profiles_migration(cursor)
    run_profile_following_migrations(cursor)
    run_instagram_profile_ai_migrations(cursor)

    conn.commit()
