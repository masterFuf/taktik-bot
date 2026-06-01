"""Database and device session helpers for the Instagram scraping bridge."""

from __future__ import annotations

import json

from loguru import logger

from bridges.common.device.connection import ConnectionService
from taktik.core.database import configure_db_service


def configure_scraping_database() -> None:
    try:
        configure_db_service()
        logger.info("Database service configured (local SQLite)")
    except Exception as e:
        logger.warning(f"Could not configure database service: {e}")


def create_scraping_connection(device_id: str) -> ConnectionService:
    return ConnectionService(device_id)


def connect_scraping_device(connection: ConnectionService):
    if not connection.connect():
        print(json.dumps({"success": False, "error": "Failed to connect to device"}))
        return None

    return connection.device_manager


def disconnect_scraping_connection(connection: ConnectionService) -> None:
    try:
        connection.disconnect()
    except Exception:
        pass
