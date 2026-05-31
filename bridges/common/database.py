"""Compatibility database helpers shared across bridge scripts.

Bridge modules keep importing this file, but SQLite ownership lives in
``taktik.core.database``.
"""

from taktik.core.database.local.paths import get_default_database_path
from taktik.core.database.messaging import SentDMService
from taktik.core.database.repositories import get_repository


def get_db_path() -> str:
    """Get the path to the local SQLite database."""
    return get_default_database_path()


__all__ = ["SentDMService", "get_db_path", "get_repository"]
