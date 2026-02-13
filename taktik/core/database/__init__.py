"""
Database package for TAKTIK Bot.

All data is stored locally in SQLite (%APPDATA%/taktik-desktop/taktik-data.db).
See README.md in this directory for full documentation.

Structure:
    database/
    ├── __init__.py         ← Public API (this file)
    ├── models.py           ← Data models (InstagramProfile, etc.)
    ├── local/
    │   ├── service.py      ← SQLite engine (LocalDatabaseService)
    │   └── client.py       ← Public client (LocalDatabaseClient)
    └── repositories/       ← Repository pattern for data access
"""

from .models import InstagramProfile
from .local.service import LocalDatabaseService, get_local_database
from .local.client import LocalDatabaseClient, get_database_client

db_service = None


def configure_db_service(**kwargs):
    """Configure the database service. Returns LocalDatabaseClient."""
    global db_service
    db_service = LocalDatabaseClient()
    return db_service


def get_db_service() -> LocalDatabaseClient:
    """Get the database service singleton. Call configure_db_service() first."""
    if db_service is None:
        raise ValueError("Database service not configured. Call configure_db_service() first.")
    return db_service


__all__ = [
    'LocalDatabaseService',
    'LocalDatabaseClient',
    'InstagramProfile',
    'configure_db_service',
    'get_db_service',
    'get_local_database',
    'get_database_client',
]
