"""Repository factory helpers for standalone bridge entrypoints."""

from __future__ import annotations

import os
import sqlite3
from typing import TypeVar

from taktik.core.database.local.paths import get_default_database_path

TRepository = TypeVar("TRepository")


def get_repository(repo_class: type[TRepository], db_path: str | None = None) -> TRepository:
    """Instantiate a repository connected to the local SQLite database."""
    resolved_db_path = db_path or get_default_database_path()
    if not os.path.exists(resolved_db_path):
        raise FileNotFoundError(f"Database not found at {resolved_db_path}")

    conn = sqlite3.connect(resolved_db_path)
    conn.row_factory = sqlite3.Row
    return repo_class(conn)


__all__ = ["get_repository"]
