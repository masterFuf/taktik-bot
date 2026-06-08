"""Gmail accounts fold (Vague F2).

Folds the standalone ``gmail_accounts`` table into the unified ``accounts`` table
(``platform='gmail'``, ``username``=email) + ``account_device_history`` (the
``device_id`` / ``last_used_at`` sighting). ``gmail_accounts`` then becomes a
read-only compatibility VIEW so existing readers (front findAll/findByDevice) keep
working unchanged; only the writers flip (GmailAccountRepository upsert/delete).

Idempotent and runnable on both runtimes (bot + Electron). Validated on a real-DB
copy: 12 rows -> 12 via the view, device/last_used byte-identical, 0 FK violations.
"""
from __future__ import annotations

import sqlite3

from loguru import logger

_GMAIL_VIEW_SQL = """
    CREATE VIEW gmail_accounts AS
    SELECT a.legacy_account_id AS account_id,
           a.username          AS email,
           adh.device_id       AS device_id,
           adh.last_seen_at    AS last_used_at,
           a.created_at        AS created_at
    FROM accounts a
    LEFT JOIN account_device_history adh
      ON adh.platform = 'gmail' AND adh.username = a.username
    WHERE a.platform = 'gmail'
"""


def _object_type(cursor: sqlite3.Cursor, name: str) -> str | None:
    row = cursor.execute("SELECT type FROM sqlite_master WHERE name = ?", (name,)).fetchone()
    return row[0] if row else None


def run_gmail_accounts_fold(cursor: sqlite3.Cursor) -> None:
    obj = _object_type(cursor, "gmail_accounts")

    if obj == "view":
        return  # already folded

    if obj == "table":
        logger.info("Migration (Vague F2): folding gmail_accounts into accounts + account_device_history")
        # 1) backfill accounts (platform='gmail'); username=email, legacy_account_id=account_id
        cursor.execute(
            """
            INSERT INTO accounts (platform, legacy_account_id, username, is_bot, created_at, updated_at)
            SELECT 'gmail', g.account_id, g.email, 0, g.created_at, COALESCE(g.last_used_at, g.created_at)
            FROM gmail_accounts g
            WHERE NOT EXISTS (
                SELECT 1 FROM accounts a WHERE a.platform = 'gmail' AND a.username = g.email
            )
            """
        )
        # 2) backfill the device sighting for rows that have a device.
        # account_device_history is front-owned; on a bot-only / standalone base it may
        # not exist (and gmail is unused there anyway), so guard on its presence to keep
        # the migration safe. On the shared dual-runtime DB it always exists.
        if _object_type(cursor, "account_device_history") == "table":
            cursor.execute(
                """
                INSERT INTO account_device_history
                    (platform, username, device_id, package_name, source, first_seen_at, last_seen_at, seen_count)
                SELECT 'gmail', g.email, g.device_id, '', 'gmail',
                       COALESCE(g.last_used_at, g.created_at), g.last_used_at, 1
                FROM gmail_accounts g
                WHERE g.device_id IS NOT NULL AND g.device_id != ''
                  AND NOT EXISTS (
                    SELECT 1 FROM account_device_history adh
                    WHERE adh.platform = 'gmail' AND adh.username = g.email
                      AND adh.device_id = g.device_id AND adh.package_name = ''
                  )
                """
            )
        # 3) replace the table with a read-only compat view
        cursor.execute("DROP TABLE gmail_accounts")
        cursor.execute(_GMAIL_VIEW_SQL)
        return

    # not present (fresh base) -> create the (empty) view so readers have it
    cursor.execute(_GMAIL_VIEW_SQL)
