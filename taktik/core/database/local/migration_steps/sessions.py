"""Unified sessions table migration (Vague B, platform axis).

Phase A (additive, non-destructive): create a single local `sessions_unified`
table that folds `sessions` (Instagram) and `tiktok_sessions` (TikTok) via a
`platform` column (lossless superset of the two legacy column sets), and backfill
it idempotently. The legacy tables stay untouched (still written and Turso-synced);
the unified table is local-only for now (cf. database-restructure-spec.md).

Transitional name: the target end-state is `sessions`, reached by dropping the
legacy tables and renaming in a later gated phase. `scraping_sessions` /
`smart_comment_sessions` are a later sub-lot.

Column-aware copy: the bot-standalone legacy schemas lag the shared/real DB (the
front adds `ai_*` / `stats_*` to `sessions` and `videos_watched` to
`tiktok_sessions`). The backfill/mirror copy only the legacy columns that actually
exist so the migration runs on both schemas without losing real data on the shared
DB; missing columns fall back to the unified table's defaults. The shared
`build_session_copy_sql` helper is reused by the session repositories' mirrors.
"""

from __future__ import annotations

import sqlite3
from typing import List

from loguru import logger

# Candidate columns copied verbatim (same name in legacy table and sessions_unified).
IG_SESSION_COLS: List[str] = [
    "account_id", "session_name", "target_type", "target", "start_time", "end_time",
    "duration_seconds", "config_used", "status", "error_message", "synced_to_api",
    "ai_total_cost_usd", "ai_profiles_analyzed", "ai_posts_analyzed", "ai_comments_generated",
    "stats_total_interactions", "stats_likes", "stats_follows", "stats_unfollows",
    "stats_comments", "stats_story_views", "stats_story_likes", "stats_profile_visits",
    "created_at", "updated_at", "sync_id",
]
TT_SESSION_COLS: List[str] = [
    "account_id", "session_name", "workflow_type", "target", "start_time", "end_time",
    "duration_seconds", "config_used", "status", "error_message",
    "profiles_visited", "posts_watched", "likes", "follows", "favorites", "comments",
    "shares", "errors", "videos_watched", "created_at", "updated_at", "sync_id",
]


def _existing_columns(cursor: sqlite3.Cursor, table: str, candidates: List[str]) -> List[str]:
    try:
        present = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.OperationalError:
        return []
    return [c for c in candidates if c in present]


def build_session_copy_sql(
    cursor: sqlite3.Cursor,
    platform: str,
    legacy_table: str,
    candidate_cols: List[str],
    *,
    verb: str = "INSERT OR IGNORE",
    where: str = "",
) -> str:
    """Build a column-aware INSERT ... SELECT that copies a legacy session table
    into `sessions_unified`. Only legacy columns that actually exist are copied;
    missing columns fall back to the unified table defaults."""
    cols = _existing_columns(cursor, legacy_table, candidate_cols)
    col_list = ", ".join(["platform", "legacy_session_id", *cols])
    sel_list = ", ".join([f"'{platform}'", "session_id", *cols])
    return (
        f"{verb} INTO sessions_unified ({col_list}) "
        f"SELECT {sel_list} FROM {legacy_table} {where}".strip()
    )


def run_sessions_unification_migrations(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions_unified (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            legacy_session_id INTEGER,
            account_id INTEGER,
            session_name TEXT,
            target_type TEXT,
            workflow_type TEXT,
            target TEXT,
            start_time TEXT,
            end_time TEXT,
            duration_seconds INTEGER,
            config_used TEXT,
            status TEXT,
            error_message TEXT,
            synced_to_api INTEGER DEFAULT 0,
            ai_total_cost_usd REAL DEFAULT 0,
            ai_profiles_analyzed INTEGER DEFAULT 0,
            ai_posts_analyzed INTEGER DEFAULT 0,
            ai_comments_generated INTEGER DEFAULT 0,
            stats_total_interactions INTEGER DEFAULT 0,
            stats_likes INTEGER DEFAULT 0,
            stats_follows INTEGER DEFAULT 0,
            stats_unfollows INTEGER DEFAULT 0,
            stats_comments INTEGER DEFAULT 0,
            stats_story_views INTEGER DEFAULT 0,
            stats_story_likes INTEGER DEFAULT 0,
            stats_profile_visits INTEGER DEFAULT 0,
            profiles_visited INTEGER DEFAULT 0,
            posts_watched INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            follows INTEGER DEFAULT 0,
            favorites INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            videos_watched INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            sync_id TEXT,
            UNIQUE(platform, legacy_session_id)
        )
    """)
    try:
        cursor.execute("ALTER TABLE sessions_unified ADD COLUMN sync_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_unified_account "
            "ON sessions_unified(platform, account_id)"
        )
    except sqlite3.OperationalError:
        pass

    # Idempotent, column-aware backfill from the two legacy tables.
    try:
        cursor.execute(build_session_copy_sql(cursor, "instagram", "sessions", IG_SESSION_COLS))
    except sqlite3.OperationalError as exc:
        logger.debug(f"sessions_unified backfill (instagram) skipped: {exc}")
    try:
        cursor.execute(build_session_copy_sql(cursor, "tiktok", "tiktok_sessions", TT_SESSION_COLS))
    except sqlite3.OperationalError as exc:
        logger.debug(f"sessions_unified backfill (tiktok) skipped: {exc}")

    # Generate a sync_id for rows the legacy table left NULL (PC-local rows).
    try:
        cursor.execute(
            "UPDATE sessions_unified SET sync_id = lower(hex(randomblob(16))) WHERE sync_id IS NULL"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_unified_sync_id ON sessions_unified(sync_id)"
        )
    except sqlite3.OperationalError as exc:
        logger.debug(f"sessions_unified sync_id generation/index skipped: {exc}")
