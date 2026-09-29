"""Run of the Instagram Taktik Agent bridge, from the config `run_bridge_main` read.

The run is `run_instagram_agent`, the launcher `taktik agent run` and the handler of
`instagram.engagement.taktik_agent` call too: it reads the Instagram package of the file and asks
this bridge for the phone on it. Every failure of the bridge itself is an `error` line; the
session's own lines (`agent_status`...) come from the core launcher and the workflow.
"""

from __future__ import annotations

from loguru import logger

from bridges.common import signal_handler
from bridges.instagram.agent.ai import build_agent_ai_service
from bridges.instagram.agent.bridge import TaktikAgentBridge
from bridges.instagram.agent.session import configure_agent_database, connect_agent_bridge
from bridges.instagram.agent.stop_listener import start_agent_stop_listener
from bridges.instagram.common.ipc import _ipc
from taktik.core.social_media.instagram.workflows.agent.agent_handler import AgentRuntime, run_instagram_agent


class NotConnected(Exception):
    """The phone could not be reached; the `error` line is already out."""


def _connect(device_id: str, package_name: str = None) -> AgentRuntime:
    """The phone, on the Instagram the launcher names (a clone, or the installed one)."""
    bridge = TaktikAgentBridge(device_id, package_name=package_name)
    if not connect_agent_bridge(bridge):
        raise NotConnected()
    # Electron can request a graceful stop via stdin: {"command":"stop"}.
    start_agent_stop_listener()
    return bridge.agent_runtime()


def run_taktik_agent(config: dict) -> int:
    """Connect the device and run one autonomous Taktik Agent session."""
    device_id = config.get("deviceId")
    if not device_id:
        _ipc.error("No deviceId in config")
        return 1

    configure_agent_database()

    try:
        result = run_instagram_agent(
            config,
            connect=lambda package_name: _connect(device_id, package_name),
            ipc=_ipc,
            ai_service_factory=build_agent_ai_service,
            on_workflow=signal_handler.update_workflow,
        )
    except NotConnected:
        return 1
    except ValueError as refused:
        # Refused by the launcher before Instagram was touched; it said why on stdout.
        logger.error(f"[TaktikAgentBridge] Session refused: {refused}")
        return 1
    logger.info(f"[TaktikAgentBridge] Session finished: {result}")
    return 0 if result.get("success") else 1


class TaktikAgentRun:
    """One Taktik Agent session, from its config file."""

    def __init__(self, config: dict):
        self.config = config

    def run(self) -> int:
        return run_taktik_agent(self.config)
