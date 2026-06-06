"""Unified interactions table migration (Vague B, platform axis).

Phase A (additive, non-destructive): create a single local `interactions` table
that unifies `interaction_history` (Instagram) and `tiktok_interaction_history`
(TikTok) via a `platform` column, and backfill it idempotently. The legacy
tables stay untouched (still written and still Turso-synced); the unified table
is local-only for now (cf. database-restructure-spec.md, Turso strategy Phase A).
"""

from __future__ import annotations

import sqlite3

from loguru import logger


def _has_column(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    try:
        return any(row[1] == column for row in cursor.execute(f"PRAGMA table_info({table})").fetchall())
    except sqlite3.OperationalError:
        return False


def run_interactions_unification_migrations(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            legacy_id INTEGER,
            session_id INTEGER,
            account_id INTEGER,
            profile_id INTEGER,
            interaction_type TEXT NOT NULL,
            success INTEGER DEFAULT 1,
            content TEXT,
            video_id TEXT,
            interaction_time TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now')),
            sync_id TEXT,
            UNIQUE(platform, legacy_id)
        )
    """)
    # sync_id carries the legacy row's global id for the later Turso cross-device
    # sync (Phase B). Idempotent ALTER for bases created before this column.
    try:
        cursor.execute("ALTER TABLE interactions ADD COLUMN sync_id TEXT")
    except sqlite3.OperationalError:
        pass
    for stmt in (
        "CREATE INDEX IF NOT EXISTS idx_interactions_account ON interactions(platform, account_id, interaction_type)",
        "CREATE INDEX IF NOT EXISTS idx_interactions_profile ON interactions(platform, profile_id)",
        "CREATE INDEX IF NOT EXISTS idx_interactions_time ON interactions(interaction_time)",
    ):
        try:
            cursor.execute(stmt)
        except sqlite3.OperationalError:
            pass

    # Idempotent backfill from the two legacy tables (UNIQUE(platform, legacy_id)).
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO interactions
                (platform, legacy_id, session_id, account_id, profile_id,
                 interaction_type, success, content, video_id, interaction_time, created_at)
            SELECT 'instagram', id, session_id, account_id, profile_id,
                   interaction_type, success, content, NULL, interaction_time, interaction_time
            FROM interaction_history
        """)
        if _has_column(cursor, "interaction_history", "sync_id"):
            cursor.execute(
                "UPDATE interactions SET sync_id = (SELECT ih.sync_id FROM interaction_history ih "
                "WHERE ih.id = interactions.legacy_id) WHERE platform = 'instagram' AND sync_id IS NULL"
            )
    except sqlite3.OperationalError as exc:
        logger.debug(f"interactions backfill (instagram) skipped: {exc}")
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO interactions
                (platform, legacy_id, session_id, account_id, profile_id,
                 interaction_type, success, content, video_id, interaction_time, created_at)
            SELECT 'tiktok', id, session_id, account_id, profile_id,
                   interaction_type, success, content, video_id, interaction_time, interaction_time
            FROM tiktok_interaction_history
        """)
        if _has_column(cursor, "tiktok_interaction_history", "sync_id"):
            cursor.execute(
                "UPDATE interactions SET sync_id = (SELECT tih.sync_id FROM tiktok_interaction_history tih "
                "WHERE tih.id = interactions.legacy_id) WHERE platform = 'tiktok' AND sync_id IS NULL"
            )
    except sqlite3.OperationalError as exc:
        logger.debug(f"interactions backfill (tiktok) skipped: {exc}")

    # Generate a sync_id for rows the legacy table left NULL (legacy column has no
    # default; these rows are PC-local and never cross-device synced via legacy).
    try:
        cursor.execute(
            "UPDATE interactions SET sync_id = lower(hex(randomblob(16))) WHERE sync_id IS NULL"
        )
    except sqlite3.OperationalError as exc:
        logger.debug(f"interactions sync_id generation skipped: {exc}")
