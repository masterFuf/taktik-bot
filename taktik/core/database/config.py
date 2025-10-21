"""Database configuration for Taktik Instagram using REST API."""

import os
from dotenv import load_dotenv

load_dotenv()

from ..config.api_endpoints import get_api_url

API_CONFIG = {
    'api_url': get_api_url(),
    'api_key': os.getenv('API_SECRET_KEY'),
    'use_api_only': True
}
