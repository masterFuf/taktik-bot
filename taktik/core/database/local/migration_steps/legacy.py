"""Legacy table cleanup migrations."""

from __future__ import annotations

import sqlite3

from loguru import logger


LEGACY_DISCOVERY_TABLES = (
    "discovery_interactions",
    "discovered_profiles",
    "discovery_progress",
    "discovery_templates",
    "discovery_campaigns",
)


def drop_legacy_discovery_tables(cursor: sqlite3.Cursor) -> None:
    """Drop obsolete Discovery workflow tables if an old local DB still has them."""
    existing = {
        row[0]
        for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'discovery_%'"
        ).fetchall()
    }

    for table in LEGACY_DISCOVERY_TABLES:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    removed = sorted(existing.intersection(LEGACY_DISCOVERY_TABLES))
    if removed:
        logger.info(f"Migration: dropped legacy Discovery tables: {', '.join(removed)}")
