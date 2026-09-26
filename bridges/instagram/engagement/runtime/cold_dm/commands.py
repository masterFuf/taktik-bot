"""CLI/config command handling for the Instagram Cold DM bridge.

The run is `run_instagram_cold_dm`, the launcher the Agent handler `instagram.engagement.coldDm` (and
so the CLI) calls too, called by name so the app's config contract test can follow the payload. The
bridge keeps its entry (config file, IP rotation, the final JSON), its connection (the bridges'
clone-aware, facade-wrapped device) and its stdout, `session_start` included.
"""

from __future__ import annotations

import json
import sys

from bridges.common.device.network import enforce_pre_session_ip_rotation
from bridges.common.input.keyboard import KeyboardService
from bridges.instagram.engagement.runtime.cold_dm.progress import emit_cold_dm_progress
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.runtime.ipc import _ipc, logger


def run_cold_dm_cli(args: list[str]) -> None:
    """Load Cold DM config from file and run the workflow."""
    if len(args) < 1:
        logger.error("Usage: cold_dm_bridge.py <config_file>")
        sys.exit(1)

    config_file = args[0]

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        device_id = config["deviceId"]
        package_name = config.get("packageName")
        logger.info(
            f"Starting Cold DM workflow for device: {device_id}"
            + (f" (package: {package_name})" if package_name else "")
        )

        # The page offers "reset IP before the run"; until now nothing here read it. Done before
        # connecting, so the app is never opened on the IP the previous account just used.
        if not enforce_pre_session_ip_rotation(config, device_id, ipc=_ipc, label="Cold DM"):
            print(json.dumps({"success": False, "error": "IP rotation failed"}))
            sys.exit(1)

        keyboard = KeyboardService(device_id)
        connection = InstagramBridgeBase(device_id, package_name=package_name)

        if not connection.connect():
            logger.error(f"Failed to connect to device {device_id}")
            print(json.dumps({"success": False, "error": "Failed to connect to device"}))
            sys.exit(1)

        from taktik.core.social_media.instagram.workflows.cold_dm.agent_handler import (
            ColdDmRuntime,
            run_instagram_cold_dm,
        )

        result = run_instagram_cold_dm(
            config,
            runtime=ColdDmRuntime(
                device=connection.device,
                device_manager=connection.device_manager,
                keyboard=keyboard,
                restart=connection.restart,
            ),
            progress=emit_cold_dm_progress,
            ai_ipc=_ipc,
            on_session_start=_ipc.session_start,
        )

        print(json.dumps({
            "success": result.get("success", False),
            "dmsSent": result.get("dms_sent", 0),
            "dmsSuccess": result.get("dms_success", 0),
            "dmsFailed": result.get("dms_failed", 0),
            "error": result.get("error"),
            **({"stopReason": result["stop_reason"]} if result.get("stop_reason") else {}),
        }))

    except Exception as e:
        logger.error(f"Cold DM workflow error: {e}", exc_info=True)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
