"""Unified accounts table migration (Vague B, platform axis) — Phase A (additive).

Creates a single platform-keyed ``accounts`` table folding ``instagram_accounts``
+ ``tiktok_accounts`` (+ the operator business profile from ``account_profiles``,
whose only non-redundant column is ``bio``) and backfills it idempotently
(keyed by ``(platform, legacy_account_id)``). Additive only: the legacy tables
stay the source of truth (still read/written and Turso-synced). The reader
cutover, write flip and the drop of the legacy tables are a later QA-gated phase
(``account_id`` is referenced cross-table and Turso-synced).
"""

from __future__ import annotations

import sqlite3

from loguru import logger

# Unified columns that map 1:1 from a legacy account table (besides platform +
# legacy_account_id which are derived). Only those present in the source are copied.
_SHARED_ACCOUNT_COLUMNS = (
    "username", "is_bot", "user_id", "license_id", "display_name", "qualification_prompt",
    "niche", "product_service", "objective", "target_audience", "tone_personality",
    "preferred_language", "website", "unique_selling_point", "custom_context", "created_at",
)


def _backfill_platform(cursor: sqlite3.Cursor, source_table: str, platform: str) -> None:
    try:
        existing = {row[1] for row in cursor.execute(f"PRAGMA table_info({source_table})").fetchall()}
    except sqlite3.OperationalError:
        return
    if not existing:
        return
    cols = [c for c in _SHARED_ACCOUNT_COLUMNS if c in existing]
    target = ", ".join(["platform", "legacy_account_id", *cols])
    select = ", ".join([f"'{platform}'", "account_id", *cols])
    try:
        cursor.execute(
            f"INSERT OR IGNORE INTO accounts ({target}) SELECT {select} FROM {source_table}"
        )
    except sqlite3.OperationalError as exc:
        logger.debug(f"accounts backfill ({platform}) skipped: {exc}")


def run_accounts_unification_migrations(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            legacy_account_id INTEGER,
            username TEXT NOT NULL,
            is_bot INTEGER DEFAULT 1,
            user_id INTEGER,
            license_id INTEGER,
            display_name TEXT,
            qualification_prompt TEXT,
            bio TEXT,
            niche TEXT,
            product_service TEXT,
            objective TEXT,
            target_audience TEXT,
            tone_personality TEXT,
            preferred_language TEXT,
            website TEXT,
            unique_selling_point TEXT,
            custom_context TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            sync_id TEXT,
            UNIQUE(platform, legacy_account_id)
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_unified_username ON accounts(platform, username)")

    # The operator business columns (display_name/niche/.../qualification_prompt) are
    # Electron-added; a bot-standalone base may lack them. Build the backfill from the
    # intersection of the unified columns and the columns that actually exist in each
    # source table (account_id -> legacy_account_id), so the base columns always migrate.
    _backfill_platform(cursor, "instagram_accounts", "instagram")
    _backfill_platform(cursor, "tiktok_accounts", "tiktok")

    # Preserve account_profiles.bio (its only non-redundant column) — fill-if-empty.
    try:
        cursor.execute(
            """
            UPDATE accounts SET bio = (
                SELECT NULLIF(ap.bio, '') FROM account_profiles ap WHERE ap.account_id = accounts.legacy_account_id
            )
            WHERE platform = 'instagram'
              AND (bio IS NULL OR bio = '')
              AND EXISTS (
                  SELECT 1 FROM account_profiles ap
                  WHERE ap.account_id = accounts.legacy_account_id AND NULLIF(ap.bio, '') IS NOT NULL
              )
            """
        )
    except sqlite3.OperationalError as exc:
        logger.debug(f"accounts bio backfill skipped: {exc}")
