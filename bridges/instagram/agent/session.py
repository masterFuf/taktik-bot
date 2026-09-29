"""Database and connection helpers for the Instagram Taktik Agent bridge."""

from __future__ import annotations

from loguru import logger

from bridges.instagram.common.ipc import _ipc
from taktik.core.database import configure_db_service


def configure_agent_database() -> None:
    try:
        configure_db_service()
        logger.info("[TaktikAgentBridge] Database service configured")
    except Exception as exc:
        logger.warning(f"[TaktikAgentBridge] Could not configure DB service: {exc}")


def connect_agent_bridge(bridge) -> bool:
    if bridge.connect():
        return True

    _ipc.error("Failed to connect to device")
    return False
