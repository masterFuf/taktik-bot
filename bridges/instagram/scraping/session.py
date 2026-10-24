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


def scraping_app(connection: ConnectionService, package_name: str | None = None) -> AppService:
    """The run's Instagram (a clone when the payload names one): its clean restart before the run and
    its installed version, for the selector overrides, as the automation bridge's."""
    return AppService(connection, platform="instagram", package_override=package_name)


def disconnect_scraping_connection(connection: ConnectionService) -> None:
    try:
        connection.disconnect()
    except Exception:
        pass
