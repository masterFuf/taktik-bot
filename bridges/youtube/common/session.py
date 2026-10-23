"""Session lifecycle helpers shared by YouTube bridges."""

from dataclasses import dataclass
from typing import Any

from bridges.common.run_setup import connect_run_device
from taktik.core.shared.device.connection import ConnectionService


@dataclass
class YouTubeBridgeSession:
    """Connected device session for YouTube bridge workflows."""

    connection: ConnectionService
    device: Any


def prepare_youtube_session(device_id: str) -> YouTubeBridgeSession | None:
    """Configure DB and connect the device for YouTube workflows."""
    connection = connect_run_device(device_id)
    if connection is None:
        return None
    return YouTubeBridgeSession(connection=connection, device=connection.device)


def cleanup_youtube_app(device_id: str) -> None:
    """Stop YouTube after a bridge workflow completes."""
    from taktik.core.shared.device.app_manager import force_stop_app

    force_stop_app(device_id, "youtube")
