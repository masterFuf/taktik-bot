"""Vague C: bot resilience when profile_ai_enrichments is a compat view.

The Electron front unifies profile_ai_enrichments + profile_taxonomy_assignments
into a single ``profile_qualification`` table and turns the two legacy tables into
read-only compat views. The bot shares the same SQLite file, so its own schema /
migration steps must treat profile_ai_enrichments as a possible view (writes and
indexes on a view fail with "views may not be indexed" / "cannot modify ...").
On a bot-only standalone base the table stays real and everything runs as before.
"""
import sqlite3

import pytest

from taktik.core.database.local.schemas.enrichment import create_enrichment_indexes
from taktik.core.database.local.migration_steps.enrichment import (
    run_profile_ai_enrichment_migrations,
)


def _unify_like_front(cur: sqlite3.Cursor) -> None:
    """Reproduce the front's Vague C end-state: profile_ai_enrichments is a view
    over profile_qualification."""
    cur.execute("DROP TABLE IF EXISTS profile_ai_enrichments")
    cur.execute(
        """
        CREATE TABLE profile_qualification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            profile_id INTEGER,
            username TEXT NOT NULL,
            has_ai INTEGER NOT NULL DEFAULT 0,
            has_taxonomy INTEGER NOT NULL DEFAULT 0,
            provider TEXT, model TEXT, criteria_hash TEXT,
            ai_niche TEXT, ai_specific_niche TEXT, ai_score INTEGER, ai_classification TEXT,
            ai_profession TEXT, ai_profession_tags TEXT, ai_gender TEXT, ai_age_group TEXT,
            ai_account_based_in TEXT, location_city TEXT, location_region TEXT, analysis_json TEXT,
            enrichment_source TEXT, enrichment_created_at TEXT, enrichment_updated_at TEXT,
            UNIQUE(platform, username)
        )
        """
    )
    cur.execute(
        """
        CREATE VIEW profile_ai_enrichments AS SELECT
            id AS enrichment_id, platform, profile_id, username,
            provider, model, criteria_hash, ai_niche, ai_specific_niche, ai_score,
            ai_classification, ai_profession, ai_profession_tags, ai_gender, ai_age_group,
            ai_account_based_in, location_city, location_region, analysis_json,
            enrichment_source AS source,
            enrichment_created_at AS created_at, enrichment_updated_at AS updated_at
        FROM profile_qualification WHERE has_ai = 1
        """
    )


@pytest.fixture
def conn():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    yield con
    con.close()


def test_enrichment_migration_is_noop_over_view(conn):
    cur = conn.cursor()
    _unify_like_front(cur)
    # Must not raise (no CREATE INDEX / INSERT against the view).
    run_profile_ai_enrichment_migrations(cur)
    create_enrichment_indexes(cur)
    # profile_ai_enrichments is still a view, untouched.
    row = cur.execute(
        "SELECT type FROM sqlite_master WHERE name='profile_ai_enrichments'"
    ).fetchone()
    assert row["type"] == "view"


def test_bot_reads_enrichment_through_view(conn):
    cur = conn.cursor()
    _unify_like_front(cur)
    cur.execute(
        "INSERT INTO profile_qualification (platform, username, has_ai, ai_niche, ai_score) "
        "VALUES ('instagram', 'creator', 1, 'fitness', 88)"
    )
    cur.execute(
        "INSERT INTO profile_qualification (platform, username, has_taxonomy) "
        "VALUES ('instagram', 'tax_only', 1)"
    )
    conn.commit()
    rows = cur.execute(
        "SELECT username, ai_niche, ai_score FROM profile_ai_enrichments"
    ).fetchall()
    # Only the has_ai=1 row surfaces through the view (tax_only is filtered out).
    assert [r["username"] for r in rows] == ["creator"]
    assert rows[0]["ai_niche"] == "fitness"
    assert rows[0]["ai_score"] == 88
