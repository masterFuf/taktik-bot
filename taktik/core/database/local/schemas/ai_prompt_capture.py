"""DDL for what was ACTUALLY sent to the model, per call.

Owner: the AI domain. Source of truth = the Bot (it is the side that builds the prompt).

WHY THIS EXISTS — every other table records what the model ANSWERED. Nothing recorded what it
was ASKED. So "why was this profile filed under that sub-niche" and "why does this comment read
like that" could only ever be answered by rebuilding the prompt from today's code, which answers
a different question the moment the prompt changes: a reconstruction tells you what the CURRENT
build would have sent, not what the run did send.

TWO TABLES, AND THE REASON IS SIZE — the system prompt of a classification is ~9 KB and it is
byte-identical from one call to the next (that is precisely why it carries a cache breakpoint).
Storing it per call would write ~150 MB a month for a single distinct string, on a base already
past 3 GB. So the stable half is CONTENT-ADDRESSED: hashed once into `ai_prompt_bodies`, and each
call keeps a 64-character pointer plus the small half that actually varies.

WHAT IS NOT STORED — the image. It is already in `media` under `ai_<username>.jpg`, and a second
copy inline would put the base64 (~55 KB) back into every row, which is the cost this design
exists to avoid.

NOT SYNCED — no `sync_id`. This is local diagnostic material, it is bulky, and it describes what
one machine sent; pushing it through Turso would buy nothing and cost a lot.
"""

from __future__ import annotations

import sqlite3


def create_ai_prompt_capture_tables(cursor: sqlite3.Cursor) -> None:
    """Create the prompt-capture tables if they do not exist."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_prompt_bodies (
            -- sha256 of the body. Content-addressed: the same prompt is stored once, whatever
            -- the number of calls that used it.
            hash TEXT PRIMARY KEY,
            kind TEXT NOT NULL,                     -- 'profile' | 'comment' | 'post'
            body TEXT NOT NULL,
            chars INTEGER,
            first_seen_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now')),
            uses INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_call_captures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            kind TEXT NOT NULL,                     -- 'profile' | 'comment'
            -- What the call was about: the classified profile, or the comment's target.
            username TEXT,
            -- `posted_comments.id` when the call produced a published comment, so the capture
            -- and the comment are one row apart rather than matched on a timestamp.
            comment_id INTEGER,
            captured_at TEXT DEFAULT (datetime('now')),
            model TEXT,
            -- The stable half, by reference (-> ai_prompt_bodies.hash).
            prompt_hash TEXT,
            -- The half that varies per call: the profile's bio and counters, or the post's
            -- caption and vision description. Small, so it is kept inline and stays readable
            -- without a join.
            user_prompt TEXT,
            -- The operated account's voice AS IT WAS at that moment. A persona edited later
            -- would otherwise silently rewrite the explanation of every past comment.
            persona TEXT,
            -- Everything else that changed the call: output language, whether the engagement
            -- verdict was asked, how many taxonomy entries were injected, the anti-tic window
            -- actually used.
            meta TEXT
        )
        """
    )


def create_ai_prompt_capture_indexes(cursor: sqlite3.Cursor) -> None:
    """Create supporting indexes for the prompt captures."""
    # The explain panel reads newest-first, and drills down by profile or by comment.
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_call_captures_recent "
        "ON ai_call_captures(kind, captured_at DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_call_captures_username "
        "ON ai_call_captures(platform, kind, username)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_call_captures_comment "
        "ON ai_call_captures(comment_id) WHERE comment_id IS NOT NULL"
    )


__all__ = [
    "create_ai_prompt_capture_tables",
    "create_ai_prompt_capture_indexes",
]
