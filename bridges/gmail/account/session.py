"""Session lifecycle helpers for the Gmail account bridge."""

from dataclasses import dataclass
from typing import Any, Callable

from bridges.common.device.connection import ConnectionService


@dataclass
class GmailBridgeSession:
    """Connected device session for Gmail bridge workflows."""

    connection: ConnectionService
    device: Any


def prepare_gmail_session(
    device_id: str,
    send_status: Callable[[str, str], None],
    send_error: Callable[[str], None],
) -> GmailBridgeSession | None:
    """Configure DB and connect the device for Gmail workflows."""
    try:
        from taktik.core.database import configure_db_service

        configure_db_service()
    except Exception as exc:  # noqa: BLE001 - bridge must emit JSON errors
        send_error(f"Database setup failed: {exc}")
        return None

    send_status("connecting", f"Connecting to device {device_id}...")
    connection = ConnectionService(device_id)
    if not connection.connect():
        send_error(f"Failed to connect to device {device_id}")
        return None

    if not connection.device:
        send_error("Device object unavailable after connection")
        return None

    return GmailBridgeSession(connection=connection, device=connection.device)


def cleanup_gmail_app(device_id: str) -> None:
    """Stop Gmail after a bridge workflow completes."""
    from bridges.common.device.app_manager import force_stop_app

    force_stop_app(device_id, "gmail")
