"""
Local SQLite database module.
Contains the SQLite service (engine) and the client (public interface).
"""

from .service import LocalDatabaseService, get_local_database
from .client import LocalDatabaseClient, get_database_client

__all__ = [
    'LocalDatabaseService',
    'LocalDatabaseClient',
    'get_local_database',
    'get_database_client',
]
