"""Journal of what one account has already re-shared from another.

An agency account (`institut.rentable`) re-publishes what its owner posts from a personal
account (`cindy.dermo`). The relay runs on a timer and has no memory of its own, so without
this table it would re-share the same story on every pass — the one failure mode that is
immediately visible to every follower.

The dedup key is a SIGNATURE, not a media id: Instagram never shows the bot a story id. What
the viewer does expose is the author and the posted-time label ("5 h"), which the runtime
folds into an absolute hour. Two passes twenty minutes apart therefore read the same story as
the same signature, while tomorrow's story reads as a new one.

`status` records the outcome rather than only the successes. A story the app refused to let
us re-share ('unavailable') must not be retried forever, and it is also the measurement that
answers whether the native path is usable at all for a given source account.

Local only: this is one operator's bookkeeping for one pair of accounts, not shared state.
"""

from __future__ import annotations

import sqlite3


def run_content_relays_migrations(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_relays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            -- The account doing the re-sharing, never the one being re-shared.
            account_id INTEGER,
            platform TEXT NOT NULL DEFAULT 'instagram',
            source_username TEXT NOT NULL,
            -- Author + posted hour, as read from the story viewer. See module docstring.
            media_signature TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'story',
            -- 'relayed' | 'skipped' | 'unavailable' | 'failed'
            status TEXT NOT NULL,
            reason TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # The question asked on every pass, once per candidate story: "did we already handle this
    # one for this pair of accounts?". Unique so a double pass cannot write two verdicts.
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_content_relays_signature "
        "ON content_relays(account_id, platform, source_username, media_signature)"
    )
    # The relay journal as a page reads it: newest first, per relaying account.
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_content_relays_recent "
        "ON content_relays(account_id, created_at DESC)"
    )
