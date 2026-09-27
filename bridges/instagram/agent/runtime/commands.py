"""Run of the Instagram Taktik Agent bridge, from the config `run_bridge_main` read.

Every failure of the bridge itself is an `error` line; the session's own lines (`agent_status`...)
come from the core launcher and the workflow.
"""

from __future__ import annotations

from loguru import logger

from bridges.instagram.agent.runtime.bridge import TaktikAgentBridge
from bridges.instagram.agent.runtime.session import configure_agent_database, connect_agent_bridge
from bridges.instagram.runtime.ipc import _ipc


def run_taktik_agent(config: dict) -> int:
    """Connect the device and run one autonomous Taktik Agent session."""
    device_id = config.get("deviceId")
    if not device_id:
        _ipc.error("No deviceId in config")
        return 1

    configure_agent_database()

    bridge = TaktikAgentBridge(
        device_id=device_id,
        config=config,
        package_name=config.get("packageName"),
    )

    if not connect_agent_bridge(bridge):
        return 1

    try:
        result = bridge.run()
    except ValueError as refused:
        # Refused by the launcher before Instagram was touched; it said why on stdout.
        logger.error(f"[TaktikAgentBridge] Session refused: {refused}")
        return 1
    return 0 if result.get("success") else 1


class TaktikAgentRun:
    """One Taktik Agent session, from its config file."""

    def __init__(self, config: dict):
        self.config = config

    def run(self) -> int:
        return run_taktik_agent(self.config)
