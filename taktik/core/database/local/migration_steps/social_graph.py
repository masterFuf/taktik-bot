"""Instagram social graph migration steps."""

from __future__ import annotations

import sqlite3

from loguru import logger


def run_social_graph_sync_migrations(cursor: sqlite3.Cursor) -> None:
    """Create the unified `social_graph_sync` table, backfill it, drop the legacy ones.

    `following_sync` and `followers_sync` became one table with a direction axis, and a
    single reciprocity flag replacing the two per-side columns they each carried.

    Idempotent and safe on a populated database: creation is conditional, the backfill
    ignores rows already present, and a legacy table is dropped ONLY once its own
    backfill has gone through. Each side is handled separately, so one failing cannot
    strand the other — and a failure is logged as a warning, never swallowed, because a
    legacy table left behind means rows that never reached the unified store.
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

    # Move whatever the legacy tables still hold into social_graph_sync, then drop them.
    # social_graph_sync is the primary store since the write flip, and like the tables it
    # replaces it stays local: it is not part of the synced set.
    def _table_exists(name: str) -> bool:
        return cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    def _drain(table: str, backfill: str) -> None:
        """Backfill one legacy table, then drop it — only if the backfill went through.

        Handled per table on purpose. Sharing one guard meant a single failing side
        aborted the other and left BOTH tables in place, silently, on every boot.
        """
        if not _table_exists(table):
            return
        try:
            cursor.execute(backfill)
        except sqlite3.OperationalError as exc:
            # Keep the table. Its rows have not reached the unified store, and dropping
            # it now would lose them. Loud, because retrying alone will not fix a shape
            # mismatch — someone has to look.
            logger.warning(
                f"social_graph_sync: could not migrate `{table}` ({exc}). "
                "The table is kept as is; its rows are NOT in the unified store yet."
            )
            return
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    _drain("following_sync", """
        INSERT OR IGNORE INTO social_graph_sync
            (platform, account_id, username, direction, display_name,
             is_reciprocal, followed_by_bot, unfollowed_at, first_seen_at, last_seen_at, source)
        SELECT 'instagram', account_id, username, 'following', display_name,
               is_follower_back, followed_by_bot, unfollowed_at, first_seen_at, last_seen_at, source
        FROM following_sync
    """)
    _drain("followers_sync", """
        INSERT OR IGNORE INTO social_graph_sync
            (platform, account_id, username, direction, display_name,
             is_reciprocal, followed_by_bot, unfollowed_at, first_seen_at, last_seen_at, source)
        SELECT 'instagram', account_id, username, 'follower', display_name,
               is_following_back, 0, NULL, first_seen_at, last_seen_at, source
        FROM followers_sync
    """)


def run_profile_following_migrations(cursor: sqlite3.Cursor) -> None:
    """Ensure profile_following has FK and classification fields."""
    try:
        cursor.execute("SELECT profile_id FROM profile_following LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding profile_id to profile_following")
        cursor.execute(
            "ALTER TABLE profile_following ADD COLUMN profile_id INTEGER"
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
            "ALTER TABLE profile_following ADD COLUMN following_id INTEGER"
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
