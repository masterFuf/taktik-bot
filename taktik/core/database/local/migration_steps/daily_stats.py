"""Unified daily stats table migration (Vague B, platform axis).

Phase A (additive, non-destructive): create a single local `daily_stats_unified`
table that folds `daily_stats` (Instagram) and `tiktok_daily_stats` (TikTok) via a
`platform` column (superset of the two legacy column sets), and backfill it
idempotently. The legacy tables stay untouched (still written and Turso-synced);
the unified table is local-only for now (cf. database-restructure-spec.md).

Transitional name: the target end-state is `daily_stats`, reached by dropping the
legacy tables and renaming in a later gated phase.
"""

from __future__ import annotations

import sqlite3

from loguru import logger


def run_daily_stats_unification_migrations(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats_unified (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            account_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            total_likes INTEGER DEFAULT 0,
            total_follows INTEGER DEFAULT 0,
            total_unfollows INTEGER DEFAULT 0,
            total_comments INTEGER DEFAULT 0,
            total_profile_visits INTEGER DEFAULT 0,
            total_story_views INTEGER DEFAULT 0,
            total_story_likes INTEGER DEFAULT 0,
            total_favorites INTEGER DEFAULT 0,
            total_shares INTEGER DEFAULT 0,
            total_posts_watched INTEGER DEFAULT 0,
            total_sessions INTEGER DEFAULT 0,
            completed_sessions INTEGER DEFAULT 0,
            failed_sessions INTEGER DEFAULT 0,
            total_duration_seconds INTEGER DEFAULT 0,
            synced_to_api INTEGER DEFAULT 0,
            synced_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(platform, account_id, date)
        )
    """)
    try:
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_stats_unified_account "
            "ON daily_stats_unified(platform, account_id, date)"
        )
    except sqlite3.OperationalError:
        pass

    # Idempotent backfill from the two legacy tables (UNIQUE(platform, account_id, date)).
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO daily_stats_unified
                (platform, account_id, date, total_likes, total_follows, total_unfollows, total_comments,
                 total_profile_visits, total_story_views, total_story_likes, total_favorites, total_shares,
                 total_posts_watched, total_sessions, completed_sessions, failed_sessions,
                 total_duration_seconds, synced_to_api, synced_at, created_at, updated_at)
            SELECT 'instagram', account_id, date, total_likes, total_follows, total_unfollows, total_comments,
                   total_profile_visits, total_story_views, total_story_likes, 0, 0,
                   0, total_sessions, completed_sessions, failed_sessions,
                   total_duration_seconds, synced_to_api, synced_at, created_at, updated_at
            FROM daily_stats
        """)
    except sqlite3.OperationalError as exc:
        logger.debug(f"daily_stats_unified backfill (instagram) skipped: {exc}")
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO daily_stats_unified
                (platform, account_id, date, total_likes, total_follows, total_unfollows, total_comments,
                 total_profile_visits, total_story_views, total_story_likes, total_favorites, total_shares,
                 total_posts_watched, total_sessions, completed_sessions, failed_sessions,
                 total_duration_seconds, synced_to_api, synced_at, created_at, updated_at)
            SELECT 'tiktok', account_id, date, total_likes, total_follows, 0, total_comments,
                   total_profile_visits, 0, 0, total_favorites, total_shares,
                   total_posts_watched, total_sessions, completed_sessions, failed_sessions,
                   total_duration_seconds, 0, NULL, created_at, updated_at
            FROM tiktok_daily_stats
        """)
    except sqlite3.OperationalError as exc:
        logger.debug(f"daily_stats_unified backfill (tiktok) skipped: {exc}")
