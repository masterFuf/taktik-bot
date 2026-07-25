"""Posted-comments migration steps."""

from __future__ import annotations

import sqlite3

from loguru import logger


def run_posted_comments_migrations(cursor: sqlite3.Cursor) -> None:
    """Additive, idempotent migrations for `posted_comments`.

    A comment we publish comes in two shapes, and the table only knew the first:
      - `kind='comment'` — a comment left ON someone's post (the engagement module);
      - `kind='reply'`   — a reply to someone's COMMENT under a post, which also needs to
        record whom we answered and what they had written.

    Databases created before this step already have the table (it ships in schema.py with
    CREATE TABLE IF NOT EXISTS), so the columns must be added by ALTER for them; a fresh DB
    gets them straight from the schema and this is a no-op.
    """
    def _table_exists(name: str) -> bool:
        return cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    if not _table_exists("posted_comments"):
        return  # fresh DB: create_posted_comments_tables already includes the columns

    try:
        cursor.execute("SELECT kind FROM posted_comments LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding kind, reply_to_username, reply_to_text to posted_comments")
        # Existing rows are all engagement comments — the reply flow did not exist yet.
        cursor.execute(
            "ALTER TABLE posted_comments ADD COLUMN kind TEXT NOT NULL DEFAULT 'comment'"
        )
        cursor.execute("ALTER TABLE posted_comments ADD COLUMN reply_to_username TEXT")
        cursor.execute("ALTER TABLE posted_comments ADD COLUMN reply_to_text TEXT")

    # The column exists by now — freshly created by the schema, or just added above. The index
    # lives HERE rather than in the schema because the schema runs before migrations, so on an
    # older base it would index a column that does not exist yet.
    try:
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_posted_comments_kind "
            "ON posted_comments(platform, kind)"
        )
    except sqlite3.OperationalError:
        pass


__all__ = ["run_posted_comments_migrations"]
