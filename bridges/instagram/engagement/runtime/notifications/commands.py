"""Entry of the Instagram notifications bridge: one config file, one command.

The desktop writes the command to a JSON file and passes its path (its keys: see
`run_instagram_notifications`; `deviceId` and `packageName` are the bridge's, for its connection).
The run is `run_instagram_notifications`, the core launcher the `instagram.engagement.notifications`
handler (the CLI) calls too; the bridge keeps its connection (clone-aware device, clean restart)
and its stdout (steps, final JSON).
"""

from __future__ import annotations

import json
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


def load_notifications_bridge_config(args: list[str]) -> dict | None:
    """The command the desktop wrote, or None after saying why on stdout."""
    if not args:
        emit_notif_error("Usage: notifications_bridge <config.json>")
        return None
    try:
        with open(args[0], "r", encoding="utf-8-sig") as handle:
            config = json.load(handle)
    except Exception as exc:
        emit_notif_error(f"Failed to load config: {exc}")
        return None
    if not isinstance(config, dict):
        emit_notif_error("The notifications config must be a JSON object")
        return None
    return config


def _fail(message: str) -> None:
    emit_notif_error(message)
    sys.exit(1)


def run_notifications_cli(args: list[str]) -> None:
    """Load the config file named by `args` and run its command; the result goes to stdout."""
    config = load_notifications_bridge_config(args)
    if config is None:
        sys.exit(1)

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


__all__ = ["load_notifications_bridge_config", "run_notifications_cli"]
