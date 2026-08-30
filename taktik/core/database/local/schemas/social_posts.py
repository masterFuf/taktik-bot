"""DDL for the posts collected on target accounts.

Owner: scraping domain. Source of truth = the Bot (it is the side that opens the posts).

WHY THIS EXISTS — the `post_url` workflows need a post URL to work on, and those URLs were
typed by hand. This table is where the collector puts them: one row per post opened on a
target account, with the two numbers that say whether the post is worth a run.

WHAT IS STORED — the URL (the only thing a `post_url` workflow can navigate to), whose
post it is, and how many likes and comments it showed. Nothing else: the caption, the date
and the post type are not what this table is for.

The counters are a SNAPSHOT — a re-scan overwrites them and moves `last_scraped_at`.

KEY — `post_key`, which is NOT the URL. On Instagram the normalised URL is a fine identity: a
link copied from the share sheet carries a per-copy `?igsh=` token, and stripping it leaves a
stable canonical form, so `post_key` is that normalised URL.

TikTok has no such canonical form. Measured 2026-08-30: "Copy link" mints a WHOLE NEW short link
on every copy — four copies of one video gave `vm.tiktok.com/ZN8FUVpSM`, `ZN8FUWHSs`, `ZN8FUcEWh`,
`ZN8FUtvAr` — and no numeric video id is rendered anywhere in the accessibility tree. Keyed on the
URL, one video would be stored once per visit, `find_by_url` would never hit the row it already
held, and "have we engaged this post?" would answer no forever.

So the two things are separated: `post_key` identifies, `post_url` navigates. The URL is refreshed
on every scrape (the newest link is the one most likely to still resolve), while the key stays
put. For TikTok the key is built from what the screen DOES show stably — the author, the post
date, and a fingerprint of the caption.

`instagram_posts` once existed for this purpose and was dropped as a dead table (Vague B):
it was never written. Do not resurrect that name — this table has a writer.
"""

from __future__ import annotations

import sqlite3


def create_social_posts_tables(cursor: sqlite3.Cursor) -> None:
    """Create the collected-posts table if it does not exist."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS social_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            -- Stable identity. NOT the URL: see the module docstring. Instagram uses its
            -- normalised URL, TikTok a fingerprint, because TikTok has no canonical link.
            post_key TEXT NOT NULL,
            -- The link a post_url workflow navigates to. Refreshed on every scrape, because on
            -- TikTok the newest copy is the one most likely to still resolve.
            post_url TEXT NOT NULL,
            -- Whose post it is. Known from the profile we walked, not read off the screen.
            author_username TEXT NOT NULL,
            likes_count INTEGER,
            comments_count INTEGER,
            first_seen_at TEXT DEFAULT (datetime('now')),
            last_scraped_at TEXT DEFAULT (datetime('now')),
            sync_id TEXT,
            UNIQUE(platform, post_key)
        )
        """
    )


def create_social_posts_indexes(cursor: sqlite3.Cursor) -> None:
    """Create supporting indexes."""
    # The one read this table exists for: "this account's posts, biggest first". The counter
    # is in the index so the ORDER BY is served by the walk, not a temp B-tree.
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_social_posts_author "
        "ON social_posts(platform, author_username, likes_count DESC)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_social_posts_sync_id "
        "ON social_posts(sync_id)"
    )
    # `find_by_url` still exists and is still asked, so the URL keeps an index of its own —
    # it is simply no longer what makes a row unique.
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_social_posts_url "
        "ON social_posts(platform, post_url)"
    )


__all__ = ["create_social_posts_tables", "create_social_posts_indexes"]
