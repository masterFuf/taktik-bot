"""Session lifecycle helpers for the Gmail account bridge."""

from dataclasses import dataclass
from typing import Any

from bridges.common.run_setup import connect_run_device
from taktik.core.shared.device.connection import ConnectionService


@dataclass
class GmailBridgeSession:
    """Connected device session for Gmail bridge workflows."""

    connection: ConnectionService
    device: Any


def prepare_gmail_session(device_id: str) -> GmailBridgeSession | None:
    """Configure DB and connect the device for Gmail workflows."""
    connection = connect_run_device(device_id)
    if connection is None:
        return None
    return GmailBridgeSession(connection=connection, device=connection.device)


def cleanup_gmail_app(device_id: str) -> None:
    """Stop Gmail after a bridge workflow completes."""
    from taktik.core.shared.device.app_manager import force_stop_app

    force_stop_app(device_id, "gmail")
