"""DDL for cross-platform notifications persistence (Instagram + TikTok).

Owner: notifications domain. Source of truth = the Bot (it scans the activity feed).
One table ``notifications``: one row per distinct notification seen for one of our
accounts, deduplicated across re-scans by a synthesized content hash (notification
rows carry no stable server id, same constraint that forced ``content_hash`` on
``dm_messages``).

The shape mirrors the shared spec ``internal docs``
and must stay aligned with the Electron mirror (``front/electron/database``) since the
table is Turso-synced there. Kept additive + idempotent (CREATE IF NOT EXISTS).

SECURITY: ``body`` (the notification text) is stored but must NEVER be logged (AGENTS.md),
exactly like DM message text.
"""

from __future__ import annotations

import sqlite3


def create_notifications_tables(cursor: sqlite3.Cursor) -> None:
    """Create the notifications persistence table if it does not exist."""
    # One row per distinct notification. ``account_id`` is device-local (stripped on the
    # Turso push, replaced by account_username); ``actor_*`` are nullable because TikTok
    # surfaces section-level notifications with no per-row actor. Dedup key = content_hash.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            account_id INTEGER NOT NULL,            -- accounts.legacy_account_id (our account)
            actor_username TEXT,                    -- who liked/commented/followed (= social_profiles.username)
            actor_profile_id INTEGER,               -- social_profiles.legacy_profile_id (real @handle only, nullable)
            type TEXT,                              -- shared taxonomy (new_follower/comment_mention/...); NULL for TikTok
            raw_category TEXT,                      -- platform-specific (IG fine type, or TikTok activity|system|other)
            label TEXT,                             -- cleaned display label
            body TEXT,                              -- full row text (<=200). NEVER logged.
            relative_time TEXT,                     -- relative token ("2 j") — no absolute timestamp available
            has_action INTEGER DEFAULT 0,
            attributed INTEGER DEFAULT 0,           -- 1 if cross-referenced to one of our outgoing actions
            attribution_type TEXT,                  -- 'follow' | 'dm' | 'like' | 'comment'
            attribution_at TEXT,                    -- when our action happened (if known)
            content_hash TEXT NOT NULL,             -- sha256(platform\\naccount_id\\ntype\\nactor\\nbody) — dedup
            first_seen_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now')),
            sync_id TEXT,
            UNIQUE(platform, account_id, content_hash)
        )
        """
    )


def create_notifications_indexes(cursor: sqlite3.Cursor) -> None:
    """Create supporting indexes for the notifications table."""
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_notifications_account "
        "ON notifications(platform, account_id, last_seen_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_notifications_actor "
        "ON notifications(platform, actor_username)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_sync_id "
        "ON notifications(sync_id)"
    )


__all__ = ["create_notifications_tables", "create_notifications_indexes"]
