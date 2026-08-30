"""Social-posts migration steps."""

from __future__ import annotations

import sqlite3

from loguru import logger

from ..schemas.social_posts import create_social_posts_tables, create_social_posts_indexes


def run_social_posts_migrations(cursor: sqlite3.Cursor) -> None:
    """Bring `social_posts` back to the shape the collector actually writes.

    The table shipped for a few hours with columns built for a recognition/refresh scheme
    that was cut before it ever ran: `post_ref`, `shortcode`, `post_type`, `caption_preview`,
    `posted_at_label`, `grid_position`, `scraping_id`. Nothing ever wrote a row, so rather
    than leave every base carrying seven dead columns, the obsolete shape is replaced.

    Guarded on being EMPTY: a migration must stay safe on a populated base, and if a row ever
    appeared the drop would take real data with it. A non-empty legacy table is left alone
    and its extra columns simply stay NULL.
    """
    row = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='social_posts'"
    ).fetchone()
    if row is None:
        return

    columns = {info[1] for info in cursor.execute("PRAGMA table_info(social_posts)")}
    if "post_ref" not in columns:
        return  # already the current shape

    count = cursor.execute("SELECT COUNT(*) FROM social_posts").fetchone()[0]
    if count:
        logger.warning(
            f"social_posts carries the obsolete columns but holds {count} row(s): left as is"
        )
        return

    logger.info("Migration: rebuilding empty social_posts without its cut columns")
    cursor.execute("DROP TABLE social_posts")
    create_social_posts_tables(cursor)
    create_social_posts_indexes(cursor)


def run_social_posts_identity_migration(cursor: sqlite3.Cursor) -> None:
    """Split the post's IDENTITY from its URL.

    The table was keyed on `post_url`, which works on Instagram — its share links carry a
    per-copy token that normalisation strips, leaving a stable canonical form. It cannot work on
    TikTok: "Copy link" mints a whole new short link on every copy, so one video would be stored
    once per visit and no lookup would ever find the row it already held.

    Backfills `post_key = post_url` for existing rows, which is exactly right: every row present
    is an Instagram one, and on Instagram the normalised URL IS the identity. Nothing changes for
    them.

    SQLite cannot add a UNIQUE constraint to an existing table, so the uniqueness moves to an
    index — same guarantee, and the ON CONFLICT clause names the index columns either way.
    """
    row = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='social_posts'"
    ).fetchone()
    if row is None:
        return

    columns = {info[1] for info in cursor.execute("PRAGMA table_info(social_posts)")}
    if "post_key" in columns:
        return

    # A base can still carry the obsolete shape — the step above leaves a POPULATED legacy table
    # alone on purpose, and that shape has neither `platform` nor, sometimes, `post_url`. Adding
    # an index on columns it does not have would raise mid-migration and take the whole run with
    # it. Such a table is left exactly as it is, as the step above already decided.
    if not {"platform", "post_url"} <= columns:
        logger.warning("social_posts is on the legacy shape: post_key migration skipped")
        return

    logger.info("Migration: social_posts gains post_key, its identity apart from its URL")
    cursor.execute("ALTER TABLE social_posts ADD COLUMN post_key TEXT")
    filled = cursor.execute(
        "UPDATE social_posts SET post_key = post_url WHERE post_key IS NULL"
    ).rowcount
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_social_posts_key "
        "ON social_posts(platform, post_key)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_social_posts_url "
        "ON social_posts(platform, post_url)"
    )
    logger.info(f"Migration: {filled} post(s) keyed on their existing URL")


__all__ = ["run_social_posts_migrations", "run_social_posts_identity_migration"]
