"""CLI/config command handling for the Instagram Cold DM bridge.

The run is `run_instagram_cold_dm`, the launcher the Agent handler `instagram.engagement.coldDm` (and
so the CLI) calls too, called by name so the app's config contract test can follow the payload: it
reads the package and asks the bridge's connection for the phone on it. The bridge keeps its IP
rotation and the final JSON, its connection (the bridges' clone-aware, facade-wrapped device) and
its stdout, `session_start` included.
"""

from __future__ import annotations

import json
import sys

from bridges.common.network import enforce_pre_session_ip_rotation
from bridges.common.entrypoint import MISSING_CONFIG
from taktik.core.shared.input.keyboard import KeyboardService
from bridges.instagram.cold_dm.progress import emit_cold_dm_progress
from taktik.core.social_media.instagram.workflows.core.device import InstagramDeviceBase
from bridges.instagram.common.ipc import _ipc, logger


def print_cold_dm_result(success: bool, **fields) -> None:
    """The bridge's last line: the run's verdict, and its counters when it ran."""
    print(json.dumps({"type": "cold_dm_result", "success": success, **fields}))


def report_cold_dm_entry_error(message: str, reason: str) -> None:
    """An entry failure: a missing file is logged, an unreadable one ends in the final JSON."""
    if reason == MISSING_CONFIG:
        logger.error(message)
        return
    print_cold_dm_result(False, error=message)


def _connect(device_id: str, package_name: str = None):
    """The phone, on the Instagram the launcher names (a clone, or the installed one)."""
    from taktik.core.social_media.instagram.workflows.cold_dm.agent_handler import ColdDmRuntime

    if package_name:
        logger.info(f"Cold DM on package: {package_name}")
    connection = InstagramDeviceBase(device_id, package_name=package_name)
    if not connection.connect():
        logger.error(f"Failed to connect to device {device_id}")
        print_cold_dm_result(False, error="Failed to connect to device")
        sys.exit(1)
    return ColdDmRuntime(
        device=connection.device,
        device_manager=connection.device_manager,
        keyboard=KeyboardService(device_id),
        restart=connection.restart,
    )


class ColdDmRun:
    """One Cold DM run, from its config file (read by `run_bridge_main`)."""

    def __init__(self, config: dict):
        self.config = config

    def run(self) -> int:
        run_cold_dm(self.config)
        return 0


def run_cold_dm(config: dict) -> None:
    """Run the Cold DM workflow of `config` and print its final JSON."""
    try:
        device_id = config["deviceId"]
        logger.info(f"Starting Cold DM workflow for device: {device_id}")

        # The page offers "reset IP before the run"; until now nothing here read it. Done before
        # connecting, so the app is never opened on the IP the previous account just used.
        if not enforce_pre_session_ip_rotation(config, device_id, ipc=_ipc, label="Cold DM"):
            print_cold_dm_result(False, error="IP rotation failed")
            sys.exit(1)

        from taktik.core.social_media.instagram.workflows.cold_dm.agent_handler import run_instagram_cold_dm

        result = run_instagram_cold_dm(
            config,
            connect=lambda package_name: _connect(device_id, package_name),
            progress=emit_cold_dm_progress,
            ai_ipc=_ipc,
            on_session_start=_ipc.session_start,
        )

        print_cold_dm_result(
            result.get("success", False),
            dmsSent=result.get("dms_sent", 0),
            dmsSuccess=result.get("dms_success", 0),
            dmsFailed=result.get("dms_failed", 0),
            error=result.get("error"),
            **({"stopReason": result["stop_reason"]} if result.get("stop_reason") else {}),
        )

    except Exception as e:
        logger.error(f"Cold DM workflow error: {e}", exc_info=True)
        print_cold_dm_result(False, error=str(e))
        sys.exit(1)
