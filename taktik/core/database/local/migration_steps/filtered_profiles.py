"""Unified filtered_profiles table migration (Vague B, platform axis).

Folds ``tiktok_filtered_profiles`` into ``filtered_profiles`` via a ``platform``
column. The legacy Instagram table already carries the target name and a Turso
``sync_id``, so it is rebuilt in place (add ``platform``, drop the cross-table
foreign keys since ``profile_id`` / ``account_id`` are polymorphic across
platforms, widen the UNIQUE constraint to include ``platform``), preserving every
existing ``id`` and ``sync_id`` (no remote re-sync). The TikTok rows (never
Turso-synced) are backfilled with a generated ``sync_id``, then the legacy table
is dropped. Idempotent: the rebuild only runs while the ``platform`` column is
still missing.
"""

from __future__ import annotations

import sqlite3

from loguru import logger


def run_filtered_profiles_unification_migrations(cursor: sqlite3.Cursor) -> None:
    cols = [row[1] for row in cursor.execute("PRAGMA table_info(filtered_profiles)").fetchall()]

    if cols and "platform" not in cols:
        cursor.execute(
            """
            CREATE TABLE filtered_profiles_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL DEFAULT 'instagram',
                profile_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                filtered_at TEXT DEFAULT (datetime('now')),
                reason TEXT,
                source_type TEXT DEFAULT 'GENERAL',
                source_name TEXT DEFAULT 'unknown',
                session_id INTEGER,
                sync_id TEXT,
                UNIQUE(platform, profile_id, account_id)
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO filtered_profiles_new
                (id, platform, profile_id, account_id, username, filtered_at, reason,
                 source_type, source_name, session_id, sync_id)
            SELECT id, 'instagram', profile_id, account_id, username, filtered_at, reason,
                   source_type, source_name, session_id, sync_id
            FROM filtered_profiles
            """
        )
        cursor.execute("DROP TABLE filtered_profiles")
        cursor.execute("ALTER TABLE filtered_profiles_new RENAME TO filtered_profiles")
        logger.info("Rebuilt filtered_profiles with platform axis")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_filtered_account ON filtered_profiles(account_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_filtered_username ON filtered_profiles(username)")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_filtered_profiles_sync_id ON filtered_profiles(sync_id)"
    )

    # Backfill TikTok filtered rows (platform='tiktok', generated sync_id), then drop the twin.
    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO filtered_profiles
                (platform, profile_id, account_id, username, filtered_at, reason,
                 source_type, source_name, session_id, sync_id)
            SELECT 'tiktok', profile_id, account_id, username, filtered_at, reason,
                   source_type, source_name, session_id, lower(hex(randomblob(16)))
            FROM tiktok_filtered_profiles
            """
        )
    except sqlite3.OperationalError as exc:
        logger.debug(f"filtered_profiles tiktok backfill skipped: {exc}")
    cursor.execute("DROP TABLE IF EXISTS tiktok_filtered_profiles")
