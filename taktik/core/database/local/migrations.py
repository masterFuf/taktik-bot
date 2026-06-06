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
from .migration_steps.enrichment import run_profile_ai_enrichment_migrations
from .migration_steps.instagram import (
    run_instagram_profile_ai_migrations,
    run_instagram_profile_core_migrations,
)
from .migration_steps.legacy import drop_legacy_discovery_tables
from .migration_steps.social_graph import (
    run_profile_following_migrations,
    run_social_graph_sync_migrations,
)
from .migration_steps.tiktok import run_legacy_tiktok_scraped_profiles_migration
from .migration_steps.interactions import run_interactions_unification_migrations
from .migration_steps.daily_stats import run_daily_stats_unification_migrations
from .migration_steps.sessions import run_sessions_unification_migrations
from .migration_steps.filtered_profiles import run_filtered_profiles_unification_migrations
from .migration_steps.scraped_profiles import run_scraped_profiles_unification_migrations


def run_migrations(conn: sqlite3.Connection) -> None:
    """Run idempotent migrations against an existing local SQLite database."""
    cursor = conn.cursor()

    # Keep the historical order to avoid subtle regressions on old databases.
    run_scraped_comments_migrations(cursor)
    run_instagram_profile_core_migrations(cursor)
    run_scraping_session_migrations(cursor)
    run_scraped_profile_migrations(cursor)
    run_legacy_tiktok_scraped_profiles_migration(cursor)
    run_scraped_profiles_unification_migrations(cursor)
    run_profile_following_migrations(cursor)
    run_social_graph_sync_migrations(cursor)
    run_interactions_unification_migrations(cursor)
    run_daily_stats_unification_migrations(cursor)
    run_sessions_unification_migrations(cursor)
    run_filtered_profiles_unification_migrations(cursor)
    run_instagram_profile_ai_migrations(cursor)
    run_profile_ai_enrichment_migrations(cursor)
    drop_legacy_discovery_tables(cursor)

    conn.commit()
