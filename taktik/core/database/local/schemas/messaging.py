"""DDL for cross-platform direct-message persistence (Instagram + TikTok).

Owner: messaging domain. Source of truth = the Bot (it reads/sends DMs).
Two tables:
  - ``dm_threads``  : one row per conversation (our account x interlocutor).
  - ``dm_messages`` : the messages of those conversations (append-only).

The shape mirrors the shared spec ``internal docs``
and must stay aligned with the Electron mirror (``front/electron/database``) since
the tables are Turso-synced there. Kept additive + idempotent (CREATE IF NOT EXISTS).
"""

from __future__ import annotations

import sqlite3


def create_messaging_tables(cursor: sqlite3.Cursor) -> None:
    """Create the DM persistence tables if they do not exist."""
    # One row per conversation. Keyed by (platform, our account, interlocutor).
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dm_threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            account_id INTEGER NOT NULL,            -- accounts.legacy_account_id (our account)
            partner_username TEXT NOT NULL,         -- the interlocutor (= social_profiles.username)
            partner_profile_id INTEGER,             -- social_profiles.legacy_profile_id (nullable)
            external_thread_id TEXT,                -- TikTok conversation id / IG inbox_username
            is_group INTEGER DEFAULT 0,
            can_reply INTEGER DEFAULT 1,
            last_message_text TEXT,
            last_message_at TEXT,
            last_message_is_ours INTEGER DEFAULT 0,
            unread_count INTEGER DEFAULT 0,         -- TikTok; 0 on IG (not detected from the UI)
            message_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            sync_id TEXT,
            UNIQUE(platform, account_id, partner_username)
        )
        """
    )

    # The messages. Append-only. No stable server-side message id is available from the
    # mobile UI, so dedup on re-read uses a content hash (direction + text). Limitation:
    # two byte-identical messages in the same thread collapse to one row (acceptable for a
    # conversation-history view).
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dm_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            thread_sync_id TEXT NOT NULL,           -- link to dm_threads.sync_id (stable cross-device)
            account_id INTEGER,
            partner_username TEXT,
            direction TEXT NOT NULL,                -- 'sent' | 'received'
            msg_type TEXT DEFAULT 'text',           -- text | reel | media | sticker | gif
            text TEXT,
            content_hash TEXT NOT NULL,             -- sha256 of direction + text, for re-read dedup
            seq INTEGER DEFAULT 0,                  -- read-order index within the thread (display)
            sent_at TEXT DEFAULT (datetime('now')), -- sortable insertion datetime (sync delta cursor / fallback)
            displayed_at TEXT,                      -- raw IG date/time label for display (e.g. "Jun 12, 10:29 AM")
            ai_model TEXT,                          -- for our AI-generated replies
            ai_cost_usd REAL,
            sync_id TEXT,
            UNIQUE(platform, thread_sync_id, direction, content_hash)
        )
        """
    )


def create_messaging_indexes(cursor: sqlite3.Cursor) -> None:
    """Create supporting indexes for the DM tables."""
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_dm_threads_account "
        "ON dm_threads(platform, account_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_dm_threads_partner "
        "ON dm_threads(platform, partner_username)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_dm_threads_sync_id "
        "ON dm_threads(sync_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_dm_messages_thread "
        "ON dm_messages(thread_sync_id, seq)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_dm_messages_sync_id "
        "ON dm_messages(sync_id)"
    )


__all__ = ["create_messaging_tables", "create_messaging_indexes"]
