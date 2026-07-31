"""Sponsored posts met while browsing a feed — one row per CREATIVE, not per encounter.

The feed crawl has always recognised ads in order to skip them. This table is what turns
that throwaway signal into a corpus: whenever the crawl glides past a sponsored post, the
creative is recorded once and every later encounter only bumps `times_seen`.

The counter IS the value. A single sighting of an ad says nothing; the same creative seen
forty times over three weeks says the advertiser's budget is holding — which is the one
thing a competitor cannot fake. Deduplicating by a perceptual hash of the pixels (rather
than by advertiser or by caption) is what makes that count meaningful: the same creative
re-served under a slightly different caption is still the same creative.

It also bounds the AI bill: analysis is paid per creative, never per encounter.

Local only, deliberately. The screenshot is a blob, and media blobs sync roughly twenty
times slower than the rest — this corpus is an analysis tool for one machine, not shared
state, so nothing here is meant to travel to Turso.
"""

from __future__ import annotations

import sqlite3


def run_feed_ads_migrations(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feed_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            -- Perceptual hash of the creative: the dedup key. Two encounters of the same
            -- visual collapse onto one row whatever the caption says.
            creative_hash TEXT NOT NULL UNIQUE,
            advertiser TEXT,
            account_id INTEGER,
            platform TEXT NOT NULL DEFAULT 'instagram',
            screenshot BLOB,
            ocr_text TEXT,
            -- Filled later, out of the run: the phone must never wait on an AI call.
            ai_analysis TEXT,
            ai_analyzed_at TEXT,
            times_seen INTEGER NOT NULL DEFAULT 1,
            first_seen_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # The two reads this table exists for: "what keeps coming back" and "who advertises here".
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_ads_times_seen ON feed_ads(times_seen DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_ads_advertiser ON feed_ads(advertiser)"
    )
    # Finding what still needs analysing must not scan the blobs.
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_ads_pending_ai "
        "ON feed_ads(ai_analyzed_at) WHERE ai_analyzed_at IS NULL"
    )
