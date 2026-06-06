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
            UNIQUE(platform, legacy_id)
        )
    """)
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
    except sqlite3.OperationalError as exc:
        logger.debug(f"interactions backfill (tiktok) skipped: {exc}")
