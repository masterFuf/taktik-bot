"""DDL for account restriction signals — the observable trace that Instagram has flagged
one of our accounts.

Owner: the Bot. It is the only side that can see the signal, because the signal only
exists while walking a list on a device.

WHY A TABLE AND NOT A LOG LINE. When Instagram serves a flagged account its private
followers first, that reordering is the one measurable symptom of the flag we have (same
source, same people, same minute, two accounts: order correlation rho = +0.12, private
profiles shifted -0.63 against +0.08 for public ones, p = 0.0015). Each detection is
therefore a DATED MEASUREMENT of an account's standing, not an incident to report and
forget. Kept over time it answers the questions that matter operationally: since when is
this account affected, how often, on which sources — and above all WHEN IT STOPS, which
reads as detections ceasing on runs that used to produce them.

KNOWN BIAS, to keep in mind when reading any duration computed from this table: a signal
is only emitted for an account we actually RUN. An account left idle through its
restriction emits nothing and its recovery goes unseen, so any measured duration is an
upper bound, never the real one.
"""

from __future__ import annotations

import sqlite3


def create_account_restriction_tables(cursor: sqlite3.Cursor) -> None:
    """Create the account restriction signals table if it does not exist."""
    # One row per DETECTION (per jump), not per session: the number of jumps a run needed
    # is itself the measure of how deep the poisoned zone was, so collapsing them would
    # throw away the intensity and keep only the date.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS account_restriction_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            account_username TEXT NOT NULL,         -- the operated account, the one being flagged
            detected_at TEXT DEFAULT (datetime('now')),
            signal TEXT NOT NULL DEFAULT 'private_first_ordering',
            source_type TEXT,                       -- FOLLOWERS | HASHTAG | LIKERS
            source_name TEXT,                       -- the list being walked
            source_followers INTEGER,               -- size of that list, when known
            streak INTEGER,                         -- consecutive private profiles that triggered it
            encounter_order INTEGER,                -- how far into the list we were (profiles seen)
            jump_index INTEGER,                     -- 1st, 2nd, 3rd jump of this run
            gestures INTEGER,                       -- flings that actually moved the list
            session_id INTEGER,
            sync_id TEXT
        )
        """
    )


def create_account_restriction_indexes(cursor: sqlite3.Cursor) -> None:
    """Create supporting indexes for the account restriction signals table."""
    # The read that matters is "this account, most recent first" — the panel line, and any
    # since-when computation.
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_account_restriction_account "
        "ON account_restriction_signals(platform, account_username, detected_at)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_account_restriction_sync_id "
        "ON account_restriction_signals(sync_id)"
    )


__all__ = ["create_account_restriction_tables", "create_account_restriction_indexes"]
