"""Database management package for Taktik Instagram.

Supports two modes:
- Local SQLite database (default, privacy-focused)
- Remote API (legacy, for backwards compatibility)
"""

from .models import InstagramProfile
from .api_database_service import APIBasedDatabaseService
from .api_client import TaktikAPIClient
from .config import API_CONFIG
from .local_database import LocalDatabaseService, get_local_database
from .local_client import LocalDatabaseClient, get_database_client

db_service = None
_use_local_db = True  # Default to local database

def set_use_local_database(use_local: bool):
    """Set whether to use local database (True) or remote API (False)."""
    global _use_local_db
    _use_local_db = use_local

def configure_db_service(api_key: str, use_local: bool = None):
    """
    Configure the database service.
    
    Args:
        api_key: API key for remote operations (license, limits)
        use_local: Override for local/remote mode. If None, uses global setting.
    """
    global db_service
    
    use_local_mode = use_local if use_local is not None else _use_local_db
    
    if use_local_mode:
        # Use local SQLite + remote API for license/limits only
        client = LocalDatabaseClient(api_key=api_key)
        db_service = APIBasedDatabaseService(api_client=client)
    else:
        # Legacy: use remote API for everything
        api_client = TaktikAPIClient(api_key=api_key)
        db_service = APIBasedDatabaseService(api_client=api_client)
    
    return db_service

def get_db_service():
    if db_service is None:
        raise ValueError("Database service not configured. Call configure_db_service() with API key.")
    return db_service

__all__ = [
    'APIBasedDatabaseService',
    'TaktikAPIClient',
    'LocalDatabaseService',
    'LocalDatabaseClient',
    'InstagramProfile',
    'configure_db_service',
    'get_db_service',
    'get_local_database',
    'get_database_client',
    'set_use_local_database',
    'API_CONFIG'
]
