"""What a bridge prepares before its run touches the phone: the bot's base, then the connection.

The same steps, in the same words, for the account bridges (Instagram, TikTok, Gmail, YouTube), the
task bridge and the YouTube upload: `connect_run_device`. The Instagram automation opens its base by
`configure_run_database` with its own code, and connects in its runtime. A base that does not open
is said by `send_run_error` (its traceback on the line and on stderr); a phone that does not
connect, by the bridge's `error` line.
"""

from __future__ import annotations

from typing import Any, Optional

from bridges.common.bridge_base import send_error, send_status
from bridges.common.entrypoint import send_run_error
from taktik.core.shared.device.connection import ConnectionService


def configure_run_database(**extra: Any) -> bool:
    """Open the bot's base for this run; False when it does not open ("Database setup failed: ...",
    `extra` passed to `send_run_error`, such as an `error_code`)."""
    try:
        from taktik.core.database import configure_db_service

        configure_db_service()
        return True
    except Exception as exc:
        send_run_error(f"Database setup failed: {exc}", exc, **extra)
        return False


def connect_run_device(device_id: str) -> Optional[ConnectionService]:
    """The base, then the phone: the connection of the run, or None once its failure is said."""
    if not configure_run_database():
        return None

    send_status("connecting", f"Connecting to device {device_id}...")
    connection = ConnectionService(device_id)
    if not connection.connect():
        send_error(f"Failed to connect to device {device_id}")
        return None
    if not connection.device:
        send_error("Device object unavailable after connection")
        return None
    return connection


__all__ = ["configure_run_database", "connect_run_device"]
