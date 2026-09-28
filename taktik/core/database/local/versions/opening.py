"""The schema check every opening of the local database goes through, once per process.

Under the desktop app (TAKTIK_DESKTOP_PID set), the app brings the base to this build's version
before it starts any bridge: a bot that finds another version refuses instead of changing the
schema behind the app's back. On its own (CLI), the bot creates a new base at this build's version,
stamps or migrates a base it recognises, and keeps its old un-numbered steps for a version-0 base it
does not recognise (built by the bot's old steps alone, or older than 1.9.8).
"""

from __future__ import annotations

import os
import sqlite3
import threading
from typing import Dict, Mapping, Optional

from loguru import logger

from .runner import (
    ABSENT,
    BEHIND,
    CURRENT,
    EMPTY,
    LEGACY_RECOGNIZED,
    LEGACY_UNRECOGNIZED,
    TOO_NEW,
    inspect_database,
    migrate_database,
)

UNDER_APP_ENV = "TAKTIK_DESKTOP_PID"

NUMBERED = "numbered"
LEGACY = "legacy"

_checked: Dict[str, str] = {}
_lock = threading.Lock()


class SchemaNotReady(RuntimeError):
    """The base is not at this build's schema version and this process may not change it."""


def _key(db_path) -> str:
    return os.path.normcase(os.path.abspath(str(db_path)))


def ensure_schema(db_path, env: Optional[Mapping[str, str]] = None) -> str:
    """`numbered` when the base is at this build's version, `legacy` when the bot keeps its old
    un-numbered steps (on its own only). Raises SchemaNotReady otherwise. Checked once per
    process and path; nothing is written when the base is already at the version."""
    env = os.environ if env is None else env
    key = _key(db_path)
    with _lock:
        if key in _checked:
            return _checked[key]
        status = inspect_database(db_path, leave_no_side_file=False)
        under_app = bool(env.get(UNDER_APP_ENV))
        if status.state == CURRENT:
            for warning in status.warnings:
                logger.warning(f"database schema: {warning}")
            mode = NUMBERED
        elif status.state == TOO_NEW:
            raise SchemaNotReady(
                f"the database is at schema version {status.user_version}, newer than this bot "
                f"({status.target_version}): update the bot"
            )
        elif under_app:
            raise SchemaNotReady(
                f"the database is at schema version {status.user_version} ({status.state}), this bot "
                f"expects {status.target_version}: restart the desktop app, which updates it first"
            )
        elif status.state in (ABSENT, EMPTY, LEGACY_RECOGNIZED, BEHIND):
            # A new base gets the numbered schema too, as when the app creates it: the bot's old
            # steps alone built a schema of their own, without the columns the app adds to the
            # bot's tables, that nothing could stamp afterwards.
            result = migrate_database(db_path, applied_by="bot")
            if not result.success:
                raise SchemaNotReady(f"schema migration failed: {result.message}")
            mode = NUMBERED
        elif status.state == LEGACY_UNRECOGNIZED:
            mode = LEGACY
        else:
            raise SchemaNotReady(f"unknown schema state {status.state}")
        _checked[key] = mode
        return mode


def stamp_if_recognized(db_path) -> str:
    """After the old steps ran on their own: stamp the base if it now is the 1.9.8 schema."""
    status = inspect_database(db_path, leave_no_side_file=False)
    if status.state != LEGACY_RECOGNIZED:
        return LEGACY
    result = migrate_database(db_path, applied_by="bot")
    if not result.success:
        logger.warning(f"database schema left un-numbered: {result.message}")
        return LEGACY
    with _lock:
        _checked[_key(db_path)] = NUMBERED
    return NUMBERED


def open_connection(db_path, *, row_factory=sqlite3.Row, env: Optional[Mapping[str, str]] = None) -> sqlite3.Connection:
    """sqlite3.connect for the bot's direct openings, after the schema check."""
    ensure_schema(db_path, env=env)
    conn = sqlite3.connect(str(db_path))
    if row_factory is not None:
        conn.row_factory = row_factory
    return conn


def forget_checks() -> None:
    """Tests only: forget which bases this process already checked."""
    with _lock:
        _checked.clear()


__all__ = [
    "LEGACY",
    "NUMBERED",
    "SchemaNotReady",
    "UNDER_APP_ENV",
    "ensure_schema",
    "forget_checks",
    "open_connection",
    "stamp_if_recognized",
]
