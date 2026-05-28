"""Instagram social graph schema definitions."""

from __future__ import annotations

import sqlite3


def create_social_graph_tables(cursor: sqlite3.Cursor) -> None:
    """Create social graph tables and indexes."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile_following (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_username   TEXT NOT NULL,
            profile_id         INTEGER REFERENCES instagram_profiles(profile_id) ON DELETE SET NULL,
            following_username TEXT NOT NULL,
            following_id       INTEGER REFERENCES instagram_profiles(profile_id) ON DELETE SET NULL,
            session_id         TEXT,
            discovered_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(profile_username, following_username)
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_profile_following_profile "
        "ON profile_following(profile_username)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_profile_following_following "
        "ON profile_following(following_username)"
    )
