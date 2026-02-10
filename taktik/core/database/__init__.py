"""Database management package for Taktik Instagram.

Supports two modes:
- Local SQLite database (default, privacy-focused)
- Remote API (legacy, for backwards compatibility)
"""

from .models import InstagramProfile
from .api_database_service import APIBasedDatabaseService
from .config import API_CONFIG
from .local_database import LocalDatabaseService, get_local_database
from .local_client import LocalDatabaseClient, get_database_client

db_service = None

def configure_db_service(api_key: str = None, use_local: bool = None):
    """
    Configure the database service (local SQLite).
    
    Args:
        api_key: Kept for backward compat, no longer used for remote calls.
        use_local: Ignored — always uses local SQLite.
    """
    global db_service
    
    client = LocalDatabaseClient(api_key=api_key)
    db_service = APIBasedDatabaseService(api_client=client)
    
    return db_service

def get_db_service():
    if db_service is None:
        raise ValueError("Database service not configured. Call configure_db_service() with API key.")
    return db_service

__all__ = [
    'APIBasedDatabaseService',
    'LocalDatabaseService',
    'LocalDatabaseClient',
    'InstagramProfile',
    'configure_db_service',
    'get_db_service',
    'get_local_database',
    'get_database_client',
    'API_CONFIG'
]
