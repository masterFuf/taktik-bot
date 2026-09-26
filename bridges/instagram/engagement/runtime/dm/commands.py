"""Instagram DM bridge command: one config file, one command.

The desktop writes the command to a JSON file and passes its path (it used to pass positional
arguments): `{"command": "read" | "read_requests", "deviceId", "limit", "packageName"?}` or
`{"command": "send", "deviceId", "username", "message", "packageName"?}`. The run is
`run_instagram_dm`, the core launcher the `instagram.engagement.dm_read` / `dm_send` handlers (the
CLI) call too; the bridge keeps its connection and its stdout (conversation events, final JSON).
"""

from __future__ import annotations

import sys

from bridges.instagram.engagement.runtime.dm.bridge import DMBridge
from bridges.instagram.engagement.runtime.dm.events import emit_dm_error, emit_dm_json
from taktik.core.social_media.instagram.workflows.dm_inbox.agent_handler import run_instagram_dm


def report_dm_entry_error(message: str, _reason: str) -> None:
    """An entry failure (no file, unreadable file), in the bridge's own final JSON."""
    emit_dm_error(message)


class DMCommand:
    """One DM command of the desktop, from its config file (read by `run_bridge_main`)."""

    def __init__(self, config: dict):
        self.config = config

    def run(self) -> int:
        run_dm_command(self.config)
        return 0


def run_dm_command(config: dict) -> None:
    """Run the command of `config`, print the result."""
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
