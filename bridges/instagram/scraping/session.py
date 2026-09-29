"""Database and device session helpers for the Instagram scraping bridge."""

from __future__ import annotations

from loguru import logger

from taktik.core.shared.device.app_manager import AppService
from taktik.core.shared.device.connection import ConnectionService
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
    """The connected device manager, or None: the runner reports the failure."""
    if not connection.connect():
        return None

    return connection.device_manager


def scraping_installed_version(connection: ConnectionService, package_name: str | None = None):
    """The installed Instagram version reader, as the automation bridge's, for the selector overrides."""
    return AppService(connection, platform="instagram", package_override=package_name).get_installed_version


def disconnect_scraping_connection(connection: ConnectionService) -> None:
    try:
        connection.disconnect()
    except Exception:
        pass
