"""Unified social_profiles table migration (Vague B, platform axis) — Phase A (additive).

Creates a single platform-keyed ``social_profiles`` table folding
``instagram_profiles`` + ``tiktok_profiles`` and backfills it idempotently
(keyed by ``(platform, legacy_profile_id)``). The frozen legacy
``instagram_profiles.ai_*`` columns are intentionally NOT carried (superseded by
``profile_ai_enrichments``). Additive only: the legacy tables stay the source of
truth (read/written and Turso-synced). The reader cutover and the drop of the
legacy tables (+ their FK cascade) are a later QA-gated phase — the highest-risk
operation of the restructure.

The backfill is column-aware: several columns are Electron-added (geo, business,
notes), so a bot-standalone base may lack them; only columns present in the source
are copied. The renamed columns are mapped explicitly (full_name/display_name,
posts_count/videos_count).
"""

from __future__ import annotations

import sqlite3

from loguru import logger

# target_column -> source_column, per platform (only used if the source column exists).
_IG_MAP = {
    "username": "username",
    "display_name": "full_name",
    "biography": "biography",
    "followers_count": "followers_count",
    "following_count": "following_count",
    "posts_count": "posts_count",
    "is_private": "is_private",
    "is_verified": "is_verified",
    "is_business": "is_business",
    "business_category": "business_category",
    "website": "website",
    "profile_pic_path": "profile_pic_path",
    "notes": "notes",
    "account_based_in": "account_based_in",
    "date_joined": "date_joined",
    "location_city": "location_city",
    "location_region": "location_region",
    "ai_screenshot_path": "ai_screenshot_path",
    "created_at": "created_at",
    "updated_at": "updated_at",
}
_TT_MAP = {
    "username": "username",
    "display_name": "display_name",
    "biography": "biography",
    "followers_count": "followers_count",
    "following_count": "following_count",
    "posts_count": "videos_count",
    "likes_count": "likes_count",
    "is_private": "is_private",
    "is_verified": "is_verified",
    "profile_pic_path": "profile_pic_path",
    "created_at": "created_at",
    "updated_at": "updated_at",
}


def _is_table(cursor: sqlite3.Cursor, name: str) -> bool:
    row = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _backfill(cursor: sqlite3.Cursor, source_table: str, platform: str, mapping: dict) -> None:
    # Only backfill from a real legacy table (after Phase C it is a compat view).
    if not _is_table(cursor, source_table):
        return
    try:
        existing = {row[1] for row in cursor.execute(f"PRAGMA table_info({source_table})").fetchall()}
    except sqlite3.OperationalError:
        return
    if not existing:
        return
    pairs = [(tgt, src) for tgt, src in mapping.items() if src in existing]
    target = ", ".join(["platform", "legacy_profile_id", *[t for t, _ in pairs]])
    select = ", ".join([f"'{platform}'", "profile_id", *[s for _, s in pairs]])
    try:
        cursor.execute(
            f"INSERT OR IGNORE INTO social_profiles ({target}) SELECT {select} FROM {source_table}"
        )
    except sqlite3.OperationalError as exc:
        logger.debug(f"social_profiles backfill ({platform}) skipped: {exc}")


def run_social_profiles_unification_migrations(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS social_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            legacy_profile_id INTEGER,
            username TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            biography TEXT,
            followers_count INTEGER DEFAULT 0,
            following_count INTEGER DEFAULT 0,
            posts_count INTEGER DEFAULT 0,
            likes_count INTEGER DEFAULT 0,
            is_private INTEGER DEFAULT 0,
            is_verified INTEGER DEFAULT 0,
            is_business INTEGER DEFAULT 0,
            business_category TEXT,
            website TEXT,
            profile_pic_path TEXT,
            ai_screenshot_path TEXT,
            notes TEXT,
            account_based_in TEXT,
            date_joined TEXT,
            location_city TEXT,
            location_region TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            sync_id TEXT,
            UNIQUE(platform, legacy_profile_id)
        )
        """
    )
    try:
        cursor.execute("ALTER TABLE social_profiles ADD COLUMN ai_screenshot_path TEXT")
    except sqlite3.OperationalError:
        pass
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_social_profiles_username ON social_profiles(platform, username)")

    _backfill(cursor, "instagram_profiles", "instagram", _IG_MAP)
    _backfill(cursor, "tiktok_profiles", "tiktok", _TT_MAP)

    # Phase C: drop the legacy tables and replace with compatibility views over
    # social_profiles (reads unchanged). On the shared DB the Electron migration has
    # already done this before the bot connects (then these are no-ops). Guarded by
    # is-table so it never runs against the views.
    for legacy in ("instagram_profiles", "tiktok_profiles"):
        if _is_table(cursor, legacy):
            cursor.execute(f"DROP TABLE {legacy}")
    if not cursor.execute("SELECT 1 FROM sqlite_master WHERE name='instagram_profiles'").fetchone():
        cursor.execute(
            """CREATE VIEW instagram_profiles AS SELECT
                legacy_profile_id AS profile_id, username, display_name AS full_name, biography,
                followers_count, following_count, posts_count, is_private, profile_pic_path, notes,
                created_at, updated_at, is_verified, is_business, business_category, website,
                NULL AS linked_accounts, NULL AS ai_niche, NULL AS ai_score, NULL AS ai_classification,
                NULL AS ai_classified_at, ai_screenshot_path, account_based_in, date_joined, location_city,
                NULL AS ai_specific_niche, NULL AS ai_profession, NULL AS ai_profession_tags,
                NULL AS ai_gender, NULL AS ai_age_group, location_region
            FROM social_profiles WHERE platform='instagram'"""
        )
    if not cursor.execute("SELECT 1 FROM sqlite_master WHERE name='tiktok_profiles'").fetchone():
        cursor.execute(
            """CREATE VIEW tiktok_profiles AS SELECT
                legacy_profile_id AS profile_id, username, display_name, followers_count, following_count,
                likes_count, posts_count AS videos_count, is_private, is_verified, biography,
                created_at, updated_at, profile_pic_path
            FROM social_profiles WHERE platform='tiktok'"""
        )
