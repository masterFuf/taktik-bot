"""Unit tests for the unified `social_profiles` table (Vague B, platform axis — Phase A)."""

import sqlite3

from taktik.core.database.local.migration_steps.social_profiles import (
    run_social_profiles_unification_migrations,
)


def _base() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    # instagram_profiles with the Electron-added columns (shared-DB shape, incl. geo + ai_*)
    con.execute(
        """
        CREATE TABLE instagram_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            full_name TEXT DEFAULT '',
            biography TEXT,
            followers_count INTEGER DEFAULT 0,
            following_count INTEGER DEFAULT 0,
            posts_count INTEGER DEFAULT 0,
            is_private INTEGER DEFAULT 0,
            is_verified INTEGER DEFAULT 0,
            is_business INTEGER DEFAULT 0,
            business_category TEXT,
            website TEXT,
            profile_pic_path TEXT,
            notes TEXT,
            account_based_in TEXT,
            location_city TEXT,
            ai_niche TEXT, ai_score INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    # tiktok_profiles base shape (no geo/business)
    con.execute(
        """
        CREATE TABLE tiktok_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT DEFAULT '',
            followers_count INTEGER DEFAULT 0,
            following_count INTEGER DEFAULT 0,
            likes_count INTEGER DEFAULT 0,
            videos_count INTEGER DEFAULT 0,
            is_private INTEGER DEFAULT 0,
            is_verified INTEGER DEFAULT 0,
            biography TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    con.execute(
        "INSERT INTO instagram_profiles (profile_id, username, full_name, followers_count, location_city, ai_niche) "
        "VALUES (500, 'ig_user', 'IG User', 1234, 'Paris', 'fitness')"
    )
    con.execute(
        "INSERT INTO tiktok_profiles (profile_id, username, display_name, videos_count, likes_count) "
        "VALUES (500, 'tt_user', 'TT User', 42, 9999)"
    )
    con.commit()
    return con


def test_fold_both_platforms_with_renamed_columns():
    con = _base()
    run_social_profiles_unification_migrations(con.cursor())

    ig = con.execute(
        "SELECT username, display_name, followers_count, location_city FROM social_profiles "
        "WHERE platform='instagram' AND legacy_profile_id=500"
    ).fetchone()
    assert ig is not None
    assert ig["username"] == "ig_user"
    assert ig["display_name"] == "IG User"      # full_name -> display_name
    assert ig["followers_count"] == 1234
    assert ig["location_city"] == "Paris"

    tt = con.execute(
        "SELECT username, display_name, posts_count, likes_count FROM social_profiles "
        "WHERE platform='tiktok' AND legacy_profile_id=500"
    ).fetchone()
    assert tt is not None
    assert tt["username"] == "tt_user"          # same legacy id, different platform — coexist
    assert tt["posts_count"] == 42              # videos_count -> posts_count
    assert tt["likes_count"] == 9999

    # frozen ai_* columns are intentionally not carried
    cols = [r[1] for r in con.execute("PRAGMA table_info(social_profiles)").fetchall()]
    assert "ai_niche" not in cols
    assert "ai_score" not in cols

    total = con.execute("SELECT COUNT(*) AS c FROM social_profiles").fetchone()["c"]
    assert total == 2
    con.close()


def test_idempotent():
    con = _base()
    run_social_profiles_unification_migrations(con.cursor())
    run_social_profiles_unification_migrations(con.cursor())
    total = con.execute("SELECT COUNT(*) AS c FROM social_profiles").fetchone()["c"]
    assert total == 2
    con.close()
