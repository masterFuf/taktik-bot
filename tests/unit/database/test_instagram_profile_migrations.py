"""L8: the instagram_profiles column-adds never ALTER a view and never block the database."""

import sqlite3

from taktik.core.database.local.migration_steps.instagram import (
    _ensure_instagram_profile_column,
    run_instagram_profile_ai_migrations,
    run_instagram_profile_core_migrations,
)

CORE_COLUMNS = {"is_verified", "is_business", "business_category", "website", "linked_accounts",
                "account_based_in", "date_joined", "location_city"}


def _columns(conn, name):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({name})").fetchall()}


def test_a_view_missing_columns_is_left_alone_and_does_not_raise():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE social_profiles (id INTEGER PRIMARY KEY, username TEXT)")
    conn.execute("CREATE VIEW instagram_profiles AS SELECT id, username FROM social_profiles")
    cursor = conn.cursor()

    run_instagram_profile_core_migrations(cursor)
    run_instagram_profile_ai_migrations(cursor)

    assert conn.execute("SELECT type FROM sqlite_master WHERE name='instagram_profiles'").fetchone()[0] == "view"
    assert _columns(conn, "instagram_profiles") == {"id", "username"}


def test_a_table_gets_every_missing_column():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE instagram_profiles (id INTEGER PRIMARY KEY, username TEXT, website TEXT)")
    cursor = conn.cursor()

    run_instagram_profile_core_migrations(cursor)
    run_instagram_profile_ai_migrations(cursor)

    assert CORE_COLUMNS | {"ai_gender", "ai_age_group"} <= _columns(conn, "instagram_profiles")


def test_a_second_run_changes_nothing():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE instagram_profiles (id INTEGER PRIMARY KEY, username TEXT)")
    cursor = conn.cursor()
    run_instagram_profile_core_migrations(cursor)
    first = _columns(conn, "instagram_profiles")
    run_instagram_profile_core_migrations(cursor)
    assert _columns(conn, "instagram_profiles") == first


def test_a_missing_object_does_not_raise():
    conn = sqlite3.connect(":memory:")
    run_instagram_profile_core_migrations(conn.cursor())
    run_instagram_profile_ai_migrations(conn.cursor())
    assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='instagram_profiles'").fetchone() is None


def test_a_failing_alter_is_logged_not_raised():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE instagram_profiles (id INTEGER PRIMARY KEY)")
    _ensure_instagram_profile_column(conn.cursor(), "broken", "INTEGER DEFAULT (")   # invalid SQL
    assert _columns(conn, "instagram_profiles") == {"id"}


def test_a_database_error_while_probing_does_not_raise():
    class BrokenCursor:
        def execute(self, *_args):
            raise sqlite3.OperationalError("database is locked")

    _ensure_instagram_profile_column(BrokenCursor(), "website", "TEXT")
