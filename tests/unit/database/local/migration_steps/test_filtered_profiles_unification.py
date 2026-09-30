"""Unit tests for the unified `filtered_profiles` table (Vague B, platform axis)."""

import sqlite3

import pytest

from taktik.core.database.local.migration_steps.filtered_profiles import (
    run_filtered_profiles_unification_migrations,
)


def _legacy_base() -> sqlite3.Connection:
    """A raw connection mimicking an old base: pre-platform filtered_profiles +
    the legacy tiktok_filtered_profiles twin."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE filtered_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            filtered_at TEXT DEFAULT (datetime('now')),
            reason TEXT,
            source_type TEXT DEFAULT 'GENERAL',
            source_name TEXT DEFAULT 'unknown',
            session_id INTEGER,
            sync_id TEXT,
            UNIQUE(profile_id, account_id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE tiktok_filtered_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            filtered_at TEXT DEFAULT (datetime('now')),
            reason TEXT,
            source_type TEXT DEFAULT 'GENERAL',
            source_name TEXT DEFAULT 'unknown',
            session_id INTEGER,
            UNIQUE(profile_id, account_id)
        )
        """
    )
    con.execute(
        "INSERT INTO filtered_profiles (profile_id, account_id, username, reason, sync_id) "
        "VALUES (10, 1, 'spammer', 'spam', 'fixed-sync-ig')"
    )
    con.execute(
        "INSERT INTO tiktok_filtered_profiles (profile_id, account_id, username, reason) "
        "VALUES (20, 1, 'tt_spammer', 'spam')"
    )
    con.commit()
    return con


def test_fold_tiktok_and_preserve_instagram():
    con = _legacy_base()
    run_filtered_profiles_unification_migrations(con.cursor())

    # platform column added, both platforms present
    cols = [r[1] for r in con.execute("PRAGMA table_info(filtered_profiles)").fetchall()]
    assert "platform" in cols

    ig = con.execute(
        "SELECT id, sync_id FROM filtered_profiles WHERE platform = 'instagram' AND username = 'spammer'"
    ).fetchone()
    assert ig is not None
    assert ig["id"] == 1           # id preserved
    assert ig["sync_id"] == "fixed-sync-ig"  # sync_id preserved (no remote re-sync)

    tt = con.execute(
        "SELECT sync_id FROM filtered_profiles WHERE platform = 'tiktok' AND username = 'tt_spammer'"
    ).fetchone()
    assert tt is not None
    assert tt["sync_id"] is not None  # generated for the folded TikTok row

    # legacy twin dropped
    dropped = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tiktok_filtered_profiles'"
    ).fetchone()
    assert dropped is None
    con.close()


def test_unification_is_idempotent():
    con = _legacy_base()
    run_filtered_profiles_unification_migrations(con.cursor())
    run_filtered_profiles_unification_migrations(con.cursor())  # second run is a no-op

    total = con.execute("SELECT COUNT(*) AS c FROM filtered_profiles").fetchone()["c"]
    assert total == 2  # 1 IG + 1 TikTok, no duplication
    con.close()


def test_cross_platform_same_ids_coexist():
    """profile_id/account_id integer spaces overlap across platforms; the unified
    UNIQUE(platform, profile_id, account_id) must let both rows coexist."""
    con = _legacy_base()
    run_filtered_profiles_unification_migrations(con.cursor())

    # same (profile_id, account_id) as the IG row but on tiktok must be allowed
    con.execute(
        "INSERT INTO filtered_profiles (platform, profile_id, account_id, username, reason, sync_id) "
        "VALUES ('tiktok', 10, 1, 'dup_ids', 'spam', 'sync-tt-dup')"
    )
    con.commit()
    rows = con.execute(
        "SELECT platform FROM filtered_profiles WHERE profile_id = 10 AND account_id = 1 ORDER BY platform"
    ).fetchall()
    assert [r["platform"] for r in rows] == ["instagram", "tiktok"]
    con.close()
