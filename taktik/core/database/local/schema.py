"""Schema bootstrap for the TAKTIK local SQLite database.

This module keeps the public ``create_schema`` entrypoint stable while the
actual DDL is grouped by data domain under ``local/schemas``.
"""

from __future__ import annotations

import sqlite3

from .schemas.gmail import create_gmail_tables
from .schemas.enrichment import create_enrichment_tables, create_enrichment_indexes
from .schemas.instagram import create_instagram_tables, create_instagram_indexes
from .schemas.messaging import create_messaging_tables, create_messaging_indexes
from .schemas.notifications import create_notifications_tables, create_notifications_indexes
from .schemas.account_restrictions import (
    create_account_restriction_tables,
    create_account_restriction_indexes,
)
from .schemas.ai_benchmarks import (
    create_ai_benchmark_tables,
    create_ai_benchmark_indexes,
)
from .schemas.post_analysis import (
    create_post_analysis_tables,
    create_post_analysis_indexes,
)
from .schemas.posted_comments import (
    create_posted_comments_tables,
    create_posted_comments_indexes,
)
from .schemas.scraping import create_scraping_tables, create_scraping_indexes
from .schemas.social_graph import create_social_graph_tables
from .schemas.social_posts import (
    create_social_posts_tables,
    create_social_posts_indexes,
)
from .schemas.tiktok import create_tiktok_tables, create_tiktok_indexes


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all required tables if they don't exist."""
    cursor = conn.cursor()

    create_instagram_tables(cursor)
    create_tiktok_tables(cursor)
    create_scraping_tables(cursor)
    create_enrichment_tables(cursor)
    create_instagram_indexes(cursor)
    create_scraping_indexes(cursor)
    create_tiktok_indexes(cursor)
    create_enrichment_indexes(cursor)
    create_social_graph_tables(cursor)
    create_gmail_tables(cursor)
    create_messaging_tables(cursor)
    create_messaging_indexes(cursor)
    create_notifications_tables(cursor)
    create_notifications_indexes(cursor)
    create_account_restriction_tables(cursor)
    create_account_restriction_indexes(cursor)
    create_posted_comments_tables(cursor)
    create_posted_comments_indexes(cursor)
    create_post_analysis_tables(cursor)
    create_post_analysis_indexes(cursor)
    create_social_posts_tables(cursor)
    create_social_posts_indexes(cursor)
    create_ai_benchmark_tables(cursor)
    create_ai_benchmark_indexes(cursor)

    conn.commit()
