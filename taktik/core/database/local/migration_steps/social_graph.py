"""Instagram social graph migration steps."""

from __future__ import annotations

import sqlite3

from loguru import logger


def run_social_graph_sync_migrations(cursor: sqlite3.Cursor) -> None:
    """Create the unified `social_graph_sync` table and backfill it.

    Restructuring Vague B (pilote) : unifie `following_sync` + `followers_sync`
    en une seule table avec un axe `direction` ('following'|'follower') et un
    `is_reciprocal` qui remplace `is_follower_back`/`is_following_back`.
    Phase additive non destructive : les tables sources restent inchangees ; le
    backfill est idempotent (`INSERT OR IGNORE` sur la cle unique).
    """
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS social_graph_sync (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL COLLATE NOCASE,
            direction TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            is_reciprocal INTEGER DEFAULT NULL,
            followed_by_bot INTEGER DEFAULT 0,
            unfollowed_at TEXT DEFAULT NULL,
            first_seen_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now')),
            source TEXT DEFAULT 'sync',
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
            UNIQUE(platform, account_id, username, direction)
        )
    """)
    for stmt in (
        "CREATE INDEX IF NOT EXISTS idx_social_graph_sync_account ON social_graph_sync(account_id, direction)",
        "CREATE INDEX IF NOT EXISTS idx_social_graph_sync_username ON social_graph_sync(account_id, username)",
    ):
        try:
            cursor.execute(stmt)
        except sqlite3.OperationalError:
            pass

    # Idempotent backfill from the two legacy tables (non destructive).
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO social_graph_sync
                (platform, account_id, username, direction, display_name,
                 is_reciprocal, followed_by_bot, unfollowed_at, first_seen_at, last_seen_at, source)
            SELECT 'instagram', account_id, username, 'following', display_name,
                   is_follower_back, followed_by_bot, unfollowed_at, first_seen_at, last_seen_at, source
            FROM following_sync
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO social_graph_sync
                (platform, account_id, username, direction, display_name,
                 is_reciprocal, followed_by_bot, unfollowed_at, first_seen_at, last_seen_at, source)
            SELECT 'instagram', account_id, username, 'follower', display_name,
                   is_following_back, 0, NULL, first_seen_at, last_seen_at, source
            FROM followers_sync
        """)
    except sqlite3.OperationalError as exc:
        logger.debug(f"social_graph_sync backfill skipped: {exc}")


def run_profile_following_migrations(cursor: sqlite3.Cursor) -> None:
    """Ensure profile_following has FK and classification fields."""
    try:
        cursor.execute("SELECT profile_id FROM profile_following LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding profile_id to profile_following")
        cursor.execute(
            "ALTER TABLE profile_following ADD COLUMN profile_id INTEGER "
            "REFERENCES instagram_profiles(profile_id) ON DELETE SET NULL"
        )
        logger.info("Migration: Backfilling profile_id in profile_following from instagram_profiles")
        cursor.execute("""
            UPDATE profile_following
            SET profile_id = (
                SELECT ip.profile_id FROM instagram_profiles ip
                WHERE ip.username = profile_following.profile_username
            )
            WHERE profile_id IS NULL
        """)
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_profile_following_profile_id "
                "ON profile_following(profile_id)"
            )
        except sqlite3.OperationalError:
            pass

    try:
        cursor.execute("SELECT following_id FROM profile_following LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding following_id to profile_following")
        cursor.execute(
            "ALTER TABLE profile_following ADD COLUMN following_id INTEGER "
            "REFERENCES instagram_profiles(profile_id) ON DELETE SET NULL"
        )
        logger.info("Migration: Backfilling following_id in profile_following from instagram_profiles")
        cursor.execute("""
            UPDATE profile_following
            SET following_id = (
                SELECT ip.profile_id FROM instagram_profiles ip
                WHERE ip.username = profile_following.following_username
            )
            WHERE following_id IS NULL
        """)
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_profile_following_following_id "
                "ON profile_following(following_id)"
            )
        except sqlite3.OperationalError:
            pass

    try:
        cursor.execute("SELECT niche_category FROM profile_following LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding niche_category, niche, gender, classified_at to profile_following")
        cursor.execute("ALTER TABLE profile_following ADD COLUMN niche_category TEXT")
        cursor.execute("ALTER TABLE profile_following ADD COLUMN niche TEXT")
        cursor.execute("ALTER TABLE profile_following ADD COLUMN gender TEXT")
        cursor.execute("ALTER TABLE profile_following ADD COLUMN classified_at TEXT")
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_profile_following_niche_category "
                "ON profile_following(niche_category)"
            )
        except sqlite3.OperationalError:
            pass
