"""DDL for the comments WE post on other people's content (engagement comments).

Owner: engagement domain. Source of truth = the Bot (it is the one typing the comment).
Electron reads it for the session drill-down; the shape must stay aligned with the
Electron mirror (``front/electron/database``).

Why a dedicated table rather than ``interactions.content``:
``interactions`` is the action LEDGER — one row per gesture, answering "what did we do,
to whom, when, in which session". A comment is the only gesture that carries real
CONTENT plus its own production metadata (which model wrote it, what it cost, why it
was written, which post it landed on). Stuffing that into the generic ``content``
column meant none of it could be queried, priced or linked back to the post.

Why NOT ``smart_comment_replies``: that table belongs to the Smart Comment flow
(scrape the commenters under a target post, qualify them, reply to THEIR comment).
Its FK points at ``smart_comment_sessions`` — a different session table than an
engagement run — and half its columns (``comment_content`` = the comment we answered,
``is_qualified``, ``qualification_reason``, ``reply_sent``…) are meaningless here.
Reusing it would mean a nullable FK plus a column set that is NULL half the time.

``interactions`` keeps its COMMENT ledger row (counters, quotas and the Turso sync all
depend on it); this table holds the rich record beside it, joined on session + target.
"""

from __future__ import annotations

import sqlite3


def create_posted_comments_tables(cursor: sqlite3.Cursor) -> None:
    """Create the posted-comments table if it does not exist."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS posted_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            -- Who posted, under which run
            account_id INTEGER,                     -- accounts.legacy_account_id (our account)
            session_id INTEGER,                     -- the automation session that posted it
            -- Where it landed
            target_username TEXT NOT NULL,          -- the profile we commented on
            post_author TEXT,                       -- usually == target_username (differs on a feed post)
            -- Post reference. `post_ref` is the CHEAP, always-available identity (author +
            -- the moment we were on it): enough to tie several comments to the same post
            -- without any extra UI gesture. `post_url` is the real shareable link and stays
            -- NULL unless the (opt-in, best-effort) capture succeeded — grabbing it costs a
            -- share-sheet round trip, so a failure must never cost us the comment record.
            post_ref TEXT,
            post_url TEXT,
            post_caption TEXT,                      -- author's own words, as read at comment time
            post_description TEXT,                  -- vision analysis of the post, when one was run
            -- What we said
            comment_text TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'ai',      -- 'ai' | 'template' | 'custom' (operator list)
            -- How it was produced (NULL for non-AI comments)
            ai_model TEXT,
            ai_cost_usd REAL,
            ai_reasoning TEXT,                      -- the model's short "why this comment"
            language TEXT,
            posted_at TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now')),
            sync_id TEXT
        )
        """
    )


def create_posted_comments_indexes(cursor: sqlite3.Cursor) -> None:
    """Create supporting indexes for the posted-comments table."""
    # The session drill-down reads by session; the profile view reads by target.
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_posted_comments_session "
        "ON posted_comments(platform, session_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_posted_comments_target "
        "ON posted_comments(platform, target_username)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_posted_comments_account "
        "ON posted_comments(platform, account_id, posted_at)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_posted_comments_sync_id "
        "ON posted_comments(sync_id)"
    )


__all__ = ["create_posted_comments_tables", "create_posted_comments_indexes"]
