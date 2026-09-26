"""Entry of the Instagram DM bridge: one config file, one command.

The desktop writes the command to a JSON file and passes its path (it used to pass positional
arguments): `{"command": "read" | "read_requests", "deviceId", "limit", "packageName"?}` or
`{"command": "send", "deviceId", "username", "message", "packageName"?}`. The run is
`run_instagram_dm`, the core launcher the `instagram.engagement.dm_read` / `dm_send` handlers (the
CLI) call too; the bridge keeps its connection and its stdout (conversation events, final JSON).
"""

from __future__ import annotations

import json
import sys

from bridges.instagram.engagement.runtime.dm.bridge import DMBridge
from bridges.instagram.engagement.runtime.dm.events import emit_dm_error, emit_dm_json
from taktik.core.social_media.instagram.workflows.dm_inbox.agent_handler import run_instagram_dm


def load_dm_bridge_config(args: list[str]) -> dict | None:
    """The command the desktop wrote, or None after saying why on stdout."""
    if not args:
        emit_dm_error("Usage: dm_bridge.py <config.json>")
        return None
    try:
        with open(args[0], "r", encoding="utf-8-sig") as handle:
            config = json.load(handle)
    except Exception as exc:
        emit_dm_error(f"Failed to load config: {exc}")
        return None
    if not isinstance(config, dict):
        emit_dm_error("The DM config must be a JSON object")
        return None
    return config


def run_dm_cli(args: list[str]) -> None:
    """Load the config file named by `args`, run its command, print the result."""
    config = load_dm_bridge_config(args)
    if config is None:
        sys.exit(1)

    try:
        device_id = config.get("deviceId")
        if not device_id:
            emit_dm_error("deviceId is required")
            sys.exit(1)

        bridge = DMBridge(device_id, package_name=config.get("packageName"))
        if not bridge.connect():
            emit_dm_error("Failed to connect to device")
            sys.exit(1)

        result = run_instagram_dm(config, runtime=bridge, emit=lambda payload: emit_dm_json(payload, flush=True))

    except Exception as e:
        import traceback

        emit_dm_json(
            {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
        )
        sys.exit(1)

    if not result.get("success"):
        emit_dm_error(result.get("error") or "DM command failed")
        sys.exit(1)
    emit_dm_json(result)
