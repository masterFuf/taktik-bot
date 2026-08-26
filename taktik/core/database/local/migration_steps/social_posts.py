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


__all__ = ["run_social_posts_migrations"]
