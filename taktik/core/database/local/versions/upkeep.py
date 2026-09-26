"""Data upkeep the bot's old steps did at every opening, kept as is on a numbered base.

Same statements, same order, same tolerance as inside the old steps; no schema change.
"""

from __future__ import annotations

import sqlite3

from loguru import logger

from ..migration_steps.device import ensure_device_identity_row
from ..migration_steps.interactions import fill_missing_interaction_sync_ids
from ..migration_steps.scraping import collapse_duplicate_scraping_sessions
from ..migration_steps.sessions import fill_missing_session_sync_ids


def run_data_upkeep(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    collapse_duplicate_scraping_sessions(cursor)
    ensure_device_identity_row(cursor)
    try:
        fill_missing_interaction_sync_ids(cursor)
    except sqlite3.OperationalError as exc:
        logger.debug(f"interactions sync_id generation skipped: {exc}")
    try:
        fill_missing_session_sync_ids(cursor)
    except sqlite3.OperationalError as exc:
        logger.debug(f"sessions_unified sync_id generation skipped: {exc}")
    conn.commit()


__all__ = ["run_data_upkeep"]
