"""A base built from the schema and a base brought up by migration must match.

The table definitions used to exist twice — once in `schemas/`, once restated inside
`migration_steps/`. They were identical only as long as someone remembered to edit both, and they
had already begun to drift: `scraping_sessions` declared `created_at` and `sync_id` in opposite
order on each side.

That is the same defect class as the missing `scraping_sessions(scraping_type)` index found during
the P0 pass: declared in the schema, so every NEW base had it, and no migration ever gave it to an
EXISTING one. The symptom is a database whose shape depends on when it was created — the hardest
kind to reproduce, because the developer's own base is usually the fresh one.

These tests compare the two paths directly, so a future edit to one side and not the other fails
here instead of on a user's machine months later.
"""
import sqlite3

import pytest

from taktik.core.database.local.migration_steps.enrichment import (
    run_profile_ai_enrichment_migrations,
)
from taktik.core.database.local.schemas.enrichment import (
    create_enrichment_indexes,
    create_enrichment_tables,
)
from taktik.core.database.local.schemas.scraping import scraping_sessions_ddl


def columns_of(cursor, table):
    """(name, type, notnull, default, pk) per column, in declaration order."""
    return [(r[1], r[2].upper(), r[3], r[4], r[5])
            for r in cursor.execute(f"PRAGMA table_info({table})").fetchall()]


def indexes_of(cursor, table):
    rows = cursor.execute(f"PRAGMA index_list({table})").fetchall()
    out = {}
    for row in rows:
        name = row[1]
        cols = [c[2] for c in cursor.execute(f"PRAGMA index_info({name})").fetchall()]
        out[name] = (tuple(cols), bool(row[2]))  # (columns, unique)
    return out


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    yield conn.cursor()
    conn.close()


# --- profile_ai_enrichments -------------------------------------------------

def test_enrichment_table_is_identical_whether_created_or_migrated(db):
    create_enrichment_tables(db)
    create_enrichment_indexes(db)
    from_schema = columns_of(db, "profile_ai_enrichments")
    schema_indexes = indexes_of(db, "profile_ai_enrichments")

    db.execute("DROP TABLE profile_ai_enrichments")
    run_profile_ai_enrichment_migrations(db)

    assert columns_of(db, "profile_ai_enrichments") == from_schema
    assert indexes_of(db, "profile_ai_enrichments") == schema_indexes


def test_enrichment_migration_is_idempotent(db):
    run_profile_ai_enrichment_migrations(db)
    first = columns_of(db, "profile_ai_enrichments")
    run_profile_ai_enrichment_migrations(db)
    assert columns_of(db, "profile_ai_enrichments") == first


def test_enrichment_carries_its_four_lookup_indexes(db):
    create_enrichment_tables(db)
    create_enrichment_indexes(db)
    names = set(indexes_of(db, "profile_ai_enrichments"))
    assert {
        "idx_profile_ai_enrichments_lookup",
        "idx_profile_ai_enrichments_profile",
        "idx_profile_ai_enrichments_score",
        "idx_profile_ai_enrichments_updated",
    } <= names


# --- scraping_sessions ------------------------------------------------------

def test_rebuild_produces_the_same_shape_as_the_schema(db):
    """The table-rebuild migration creates the table under a temporary name."""
    db.execute(scraping_sessions_ddl())
    reference = columns_of(db, "scraping_sessions")

    db.execute(scraping_sessions_ddl("scraping_sessions_new", if_not_exists=False))
    rebuilt = columns_of(db, "scraping_sessions_new")

    assert rebuilt == reference, "the rebuild must not reorder or retype a single column"


def test_the_ddl_declares_created_at_and_sync_id_in_schema_order(db):
    """The exact pair that had drifted between the two copies."""
    db.execute(scraping_sessions_ddl())
    names = [c[0] for c in columns_of(db, "scraping_sessions")]
    assert names.index("sync_id") < names.index("created_at")


def test_the_ddl_is_not_reusable_with_an_outside_name():
    """The table name is interpolated, so it must stay internal — this documents that."""
    sql = scraping_sessions_ddl("scraping_sessions_new", if_not_exists=False)
    assert "IF NOT EXISTS" not in sql
    assert "CREATE TABLE scraping_sessions_new" in sql
