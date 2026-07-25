"""DDL for the reusable part of a post's AI analysis.

Owner: engagement domain. Source of truth = the Bot (it runs the vision call).

WHY THIS EXISTS — profile qualifications are already reused across sessions and across
accounts (see `_load_cached_qualification`), but a POST analysis was re-paid every single
time, even when the very same post had just been analysed for another account. On a fleet
where several accounts cross the same targets, that is the same vision call bought twice.

WHAT IS STORED — only the FACTS about the post: what it shows, its language, the author's
caption. Those are independent of who is looking at it, so any account can reuse them.

WHAT IS NOT STORED — the verdict ("is this relevant / should we comment"). That one is
relative to the OPERATING account's persona and must be recomputed per account; keeping it
here would be the "mix raw extraction with AI inference in the same field" anti-pattern the
bot AGENTS.md warns about. Recomputing it is cheap: it is a text-only call over facts that
are already written, instead of a fresh vision call.

KEY — `post_ref` (author + short caption hash, see instagram_post_identity). Callers must
only cache when the caption is discriminating enough to tell two posts apart; a cache miss
merely costs the call we would have made anyway, whereas a wrong hit serves the wrong post.
"""

from __future__ import annotations

import sqlite3


def create_post_analysis_tables(cursor: sqlite3.Cursor) -> None:
    """Create the post-analysis cache table if it does not exist."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS post_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            -- Identity of the analysed post (author + short caption hash).
            post_ref TEXT NOT NULL,
            post_author TEXT,
            post_caption TEXT,
            -- The FACTS, reusable by any account.
            description TEXT,                       -- vision analysis of the post
            post_language TEXT,                     -- language the post is written in
            -- What producing them cost, so a reuse can be shown as a saving.
            ai_model TEXT,
            ai_cost_usd REAL,
            -- Reuse bookkeeping.
            hit_count INTEGER DEFAULT 0,            -- how many times this analysis was reused
            analyzed_at TEXT DEFAULT (datetime('now')),
            last_used_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            sync_id TEXT,
            UNIQUE(platform, post_ref)
        )
        """
    )


def create_post_analysis_indexes(cursor: sqlite3.Cursor) -> None:
    """Create supporting indexes for the post-analysis cache."""
    # The lookup is by (platform, post_ref) — already covered by the UNIQUE constraint.
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_post_analysis_author "
        "ON post_analysis(platform, post_author)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_post_analysis_sync_id "
        "ON post_analysis(sync_id)"
    )


__all__ = ["create_post_analysis_tables", "create_post_analysis_indexes"]
