"""Unit tests for the unified `accounts` table (Vague B, platform axis — Phase A)."""

import sqlite3

from taktik.core.database.local.migration_steps.accounts import (
    run_accounts_unification_migrations,
)


def _base() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    # instagram_accounts WITH the Electron-added business columns (shared-DB shape)
    con.execute(
        """
        CREATE TABLE instagram_accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            is_bot INTEGER DEFAULT 1,
            user_id INTEGER,
            license_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            qualification_prompt TEXT, display_name TEXT, niche TEXT
        )
        """
    )
    # tiktok_accounts WITHOUT business columns (bot-standalone-ish: only base cols)
    con.execute(
        """
        CREATE TABLE tiktok_accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            is_bot INTEGER DEFAULT 1,
            user_id INTEGER,
            license_id INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    con.execute(
        """
        CREATE TABLE account_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL UNIQUE,
            bio TEXT DEFAULT ''
        )
        """
    )
    con.execute("INSERT INTO instagram_accounts (account_id, username, niche) VALUES (7, 'taktik_c3po', 'growth')")
    con.execute("INSERT INTO tiktok_accounts (account_id, username) VALUES (3, 'tt_bot')")
    con.execute("INSERT INTO account_profiles (account_id, bio) VALUES (7, 'Business bio here')")
    con.commit()
    return con


def test_backfill_both_platforms_and_bio():
    con = _base()
    run_accounts_unification_migrations(con.cursor())

    ig = con.execute(
        "SELECT username, niche, bio FROM accounts WHERE platform='instagram' AND legacy_account_id=7"
    ).fetchone()
    assert ig is not None
    assert ig["username"] == "taktik_c3po"
    assert ig["niche"] == "growth"
    assert ig["bio"] == "Business bio here"   # account_profiles.bio preserved

    tt = con.execute(
        "SELECT username FROM accounts WHERE platform='tiktok' AND legacy_account_id=3"
    ).fetchone()
    assert tt is not None
    assert tt["username"] == "tt_bot"     # base-column backfill works even without business cols

    total = con.execute("SELECT COUNT(*) AS c FROM accounts").fetchone()["c"]
    assert total == 2
    con.close()


def test_idempotent():
    con = _base()
    run_accounts_unification_migrations(con.cursor())
    run_accounts_unification_migrations(con.cursor())
    total = con.execute("SELECT COUNT(*) AS c FROM accounts").fetchone()["c"]
    assert total == 2  # no duplication
    con.close()


def test_repo_create_mirrors_into_accounts(db):
    """Creating an account through the service must mirror it into the unified
    `accounts` table (Vague B Phase A mirror-write)."""
    account_id, created = db.get_or_create_account("mirror_ig", is_bot=True)
    assert created is True

    row = db._connection.execute(
        "SELECT username FROM accounts WHERE platform='instagram' AND legacy_account_id=?",
        (account_id,),
    ).fetchone()
    assert row is not None and row[0] == "mirror_ig"

    tt_id, tt_created = db.get_or_create_tiktok_account("mirror_tt")
    assert tt_created is True
    tt = db._connection.execute(
        "SELECT username FROM accounts WHERE platform='tiktok' AND legacy_account_id=?",
        (tt_id,),
    ).fetchone()
    assert tt is not None and tt[0] == "mirror_tt"
