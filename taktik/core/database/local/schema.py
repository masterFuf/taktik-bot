"""Schema bootstrap for the TAKTIK local SQLite database.

This module keeps the public ``create_schema`` entrypoint stable while the
actual DDL is grouped by data domain under ``local/schemas``.
"""

from __future__ import annotations

import sqlite3

from .schemas.discovery import create_discovery_tables, create_discovery_indexes
from .schemas.gmail import create_gmail_tables
from .schemas.instagram import create_instagram_tables, create_instagram_indexes
from .schemas.social_graph import create_social_graph_tables
from .schemas.tiktok import create_tiktok_tables, create_tiktok_indexes


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all required tables if they don't exist."""
    cursor = conn.cursor()

    create_instagram_tables(cursor)
    create_tiktok_tables(cursor)
    create_discovery_tables(cursor)
    create_instagram_indexes(cursor)
    create_discovery_indexes(cursor)
    create_tiktok_indexes(cursor)
    create_social_graph_tables(cursor)
    create_gmail_tables(cursor)

    conn.commit()
