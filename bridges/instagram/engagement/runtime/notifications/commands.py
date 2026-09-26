"""Instagram notifications bridge command: one config file, one command.

The desktop writes the command to a JSON file and passes its path (its keys: see
`run_instagram_notifications`; `deviceId` and `packageName` are the bridge's, for its connection);
`run_bridge_main` reads it. The run is `run_instagram_notifications`, the core launcher the
`instagram.engagement.notifications` handler (the CLI) calls too; the bridge keeps its connection
(clone-aware device, clean restart) and its stdout (steps, final JSON).
"""

from __future__ import annotations

import sys

from bridges.instagram.engagement.runtime.notifications.ai import notifications_ai_service
from bridges.instagram.engagement.runtime.notifications.bridge import NotificationsBridge
from bridges.instagram.engagement.runtime.notifications.events import emit_notif_error, emit_notif_json
from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.workflows.management.notifications.agent_handler import (
    NotificationsCommandError,
    run_instagram_notifications,
)


def _connect(device_id: str, package_name: str = None, *, restart: bool = True) -> NotificationsBridge:
    bridge = NotificationsBridge(device_id, package_name=package_name)
    if not bridge.connect():
        emit_notif_error("Failed to connect to device")
        sys.exit(1)
    # Only the scan restarts Instagram (fresh state). Per-row actions (accept/ignore/reply)
    # operate on the screen the user just scanned, so they skip the costly force-stop +
    # relaunch and just navigate from the current state.
    if restart:
        bridge.restart_instagram()
    return bridge


def report_notifications_entry_error(message: str, _reason: str) -> None:
    """An entry failure (no file, unreadable file), in the bridge's own final JSON."""
    emit_notif_error(message)


class NotificationsCommand:
    """One notifications command of the desktop, from its config file (read by `run_bridge_main`)."""

    def __init__(self, config: dict):
        self.config = config

    def run(self) -> int:
        run_notifications_command(self.config)
        return 0


def _fail(message: str) -> None:
    emit_notif_error(message)
    sys.exit(1)


def run_notifications_command(config: dict) -> None:
    """Run the command of `config`; the result goes to stdout."""
    device_id = config.get("deviceId")
    package_name = config.get("packageName")
    if not device_id:
        _fail("deviceId is required")

    try:
        result = run_instagram_notifications(
            config,
            connect=lambda restart: _connect(device_id, package_name, restart=restart),
            emit=lambda payload: emit_notif_json(payload, flush=True),
            instagram_ai_service=notifications_ai_service,
        )
    except NotificationsCommandError as exc:
        _fail(str(exc))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        import traceback

        logger.error(f"notifications bridge error: {exc}")
        emit_notif_json({"success": False, "error": str(exc), "traceback": traceback.format_exc()}, flush=True)
        sys.exit(1)

    emit_notif_json(result, flush=True)


__all__ = ["NotificationsCommand", "report_notifications_entry_error", "run_notifications_command"]
