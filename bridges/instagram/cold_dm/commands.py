"""CLI/config command handling for the Instagram Cold DM bridge.

The run is `run_instagram_cold_dm`, the launcher the Agent handler `instagram.engagement.coldDm` (and
so the CLI) calls too, called by name so the app's config contract test can follow the payload: it
reads and validates the payload, then asks the bridge's connection for the phone on the package it
read. The bridge keeps the final JSON, its connection (the IP rotation, then the bridges'
clone-aware, facade-wrapped device) and its stdout, `session_start` included.
"""

from __future__ import annotations

import json
import sys

from bridges.common.network import enforce_pre_session_ip_rotation, send_network_refusal
from taktik.core.shared.device.network_door import NetworkUnreachableError
from bridges.common.entrypoint import MISSING_CONFIG
from bridges.instagram.cold_dm.progress import emit_cold_dm_progress, emit_cold_dm_sent
from taktik.core.social_media.instagram.workflows.common.device import InstagramDeviceBase
from bridges.instagram.common.ipc import _ipc, logger
from taktik.core.ai.dm_rules import AiDmTextRefused


def print_cold_dm_result(success: bool, **fields) -> None:
    """The bridge's last line: the run's verdict, and its counters when it ran."""
    print(json.dumps({"type": "cold_dm_result", "success": success, **fields}))


def report_cold_dm_entry_error(message: str, reason: str) -> None:
    """An entry failure: a missing file is logged, an unreadable one ends in the final JSON."""
    if reason == MISSING_CONFIG:
        logger.error(message)
        return
    print_cold_dm_result(False, error=message)


def _connect(config: dict, device_id: str, package_name: str = None):
    """The phone, on the Instagram the launcher names (a clone, or the installed one), on a fresh IP
    when the page asked for one.

    The launcher asks for it once the payload is read and validated: a refused payload neither
    rotates the IP nor connects. The rotation comes before the connection, so the app is never
    opened on the IP the previous account just used.
    """
    from taktik.core.social_media.instagram.workflows.cold_dm.agent_handler import ColdDmRuntime

    if not enforce_pre_session_ip_rotation(config, device_id, ipc=_ipc, label="Cold DM"):
        print_cold_dm_result(False, error="IP rotation failed")
        sys.exit(1)
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

        from taktik.core.social_media.instagram.workflows.cold_dm.agent_handler import run_instagram_cold_dm

        result = run_instagram_cold_dm(
            config,
            connect=lambda package_name: _connect(config, device_id, package_name),
            progress=emit_cold_dm_progress,
            sent=emit_cold_dm_sent,
            ai_ipc=_ipc,
            on_session_start=_ipc.session_start,
        )

        print_cold_dm_result(
            result.get("success", False),
            dmsSent=result.get("dms_sent", 0),
            dmsSuccess=result.get("dms_success", 0),
            dmsFailed=result.get("dms_failed", 0),
            dmsPending=result.get("dms_pending", 0),
            error=result.get("error"),
            textsRefused=result.get("texts_refused", 0),
            **({"stopReason": result["stop_reason"]} if result.get("stop_reason") else {}),
        )

    except NetworkUnreachableError as refused:
        # The launcher's network door, once the phone is connected: nobody was written to.
        send_network_refusal(refused, "Cold DM")
        print_cold_dm_result(False, error=str(refused))
        sys.exit(1)
    except AiDmTextRefused as refused:
        # A text written by an AI breaks the rule: refused before the phone, the reason typed.
        logger.warning(f"Cold DM refused: {refused}")
        print_cold_dm_result(False, error=str(refused), textRefusal=refused.refusal.as_line())
        sys.exit(1)
    except Exception as e:
        logger.error(f"Cold DM workflow error: {e}", exc_info=True)
        print_cold_dm_result(False, error=str(e))
        sys.exit(1)
