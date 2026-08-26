"""DDL for the catalogue of posts observed on target accounts.

Owner: scraping domain. Source of truth = the Bot (it is the side that opens the posts).

WHY THIS EXISTS — the `post_url` workflows (interact with a post's likers/commenters, or
scrape them) take their post URLs from the user, typed by hand. Nothing in the base said
which posts of a target exist, nor which one is worth the run: a post with 3 000 likers
feeds a whole session, a post with 40 does not. This table is the pool those workflows
draw from — and it is filled once per post, not once per workflow.

WHAT IS STORED — the FACTS read on the opened post: its shareable URL (the only key a
`post_url` workflow can deep-link to), its author, the like and comment counters as
displayed, a caption preview. Counters are a SNAPSHOT: a re-scrape overwrites them and
bumps `last_scraped_at`; there is deliberately no history table until a reader needs one.

IDENTITY — `post_url`, normalised (share links carry a per-copy `?igsh=` token that would
otherwise make the same post unique every time it is copied). `post_ref` (author + caption
hash, see `instagram_post_identity`) is stored alongside as the join key to `post_analysis`
(a vision analysis already paid for) and `posted_comments` (a post we already commented) —
and as the cheap pre-check that lets a scan recognise a post it already holds BEFORE paying
the share-sheet round trip for its URL.

`instagram_posts` once existed for this purpose and was dropped as a dead table (Vague B):
it was never written. Do not resurrect that name — this table has a writer.
"""

from __future__ import annotations

import sqlite3


def create_social_posts_tables(cursor: sqlite3.Cursor) -> None:
    """Create the post catalogue table if it does not exist."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS social_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            -- Canonical shareable URL: the key, and what a post_url workflow deep-links to.
            post_url TEXT NOT NULL,
            shortcode TEXT,                         -- the code inside the URL (/p/<code>/, /reel/<code>/)
            post_type TEXT,                         -- 'post' | 'reel'
            author_username TEXT NOT NULL,
            -- author + caption hash: join key with post_analysis / posted_comments, and the
            -- free pre-check that spares the share-sheet for a post already catalogued.
            post_ref TEXT,
            caption_preview TEXT,
            -- The SNAPSHOT that makes a post worth a run. Overwritten on re-scrape.
            likes_count INTEGER,
            comments_count INTEGER,
            posted_at_label TEXT,                   -- date as displayed by the app (reels expose it)
            grid_position INTEGER,                  -- 1-based cell in the author's grid when scanned
            scraping_id INTEGER,                    -- scraping_sessions row that last touched it
            first_seen_at TEXT DEFAULT (datetime('now')),
            last_scraped_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            sync_id TEXT,
            UNIQUE(platform, post_url)
        )
        """
    )


def create_social_posts_indexes(cursor: sqlite3.Cursor) -> None:
    """Create supporting indexes for the post catalogue."""
    # The catalogue read: "this author's posts, biggest first". The counter is in the index
    # so the ORDER BY is served by the walk, not a temp B-tree.
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_social_posts_author "
        "ON social_posts(platform, author_username, likes_count DESC)"
    )
    # The pre-share recognition check ("do I already hold this post?").
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_social_posts_ref "
        "ON social_posts(platform, post_ref) WHERE post_ref IS NOT NULL"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_social_posts_sync_id "
        "ON social_posts(sync_id)"
    )


__all__ = ["create_social_posts_tables", "create_social_posts_indexes"]
