"""Database management package for Taktik Instagram using REST API."""

from .models import InstagramProfile
from .api_database_service import APIBasedDatabaseService
from .api_client import TaktikAPIClient
from .config import API_CONFIG

db_service = None

def configure_db_service(api_key: str):
    global db_service
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
    'InstagramProfile',
    'configure_db_service',
    'get_db_service',
    'API_CONFIG'
]
