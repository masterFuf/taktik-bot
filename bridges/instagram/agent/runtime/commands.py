"""Run of the Instagram Taktik Agent bridge, from the config `run_bridge_main` read."""

from __future__ import annotations

import json

from bridges.instagram.agent.runtime.bridge import TaktikAgentBridge
from bridges.instagram.agent.runtime.session import configure_agent_database, connect_agent_bridge


def report_agent_entry_error(message: str, _reason: str) -> None:
    """An entry failure (no file, unreadable file), in the bridge's own final JSON."""
    print(json.dumps({"success": False, "error": message}), flush=True)


def run_taktik_agent(config: dict) -> int:
    """Connect the device and run one autonomous Taktik Agent session."""
    device_id = config.get("deviceId")
    if not device_id:
        print(json.dumps({"success": False, "error": "No deviceId in config"}), flush=True)
        return 1

    configure_agent_database()

    bridge = TaktikAgentBridge(
        device_id=device_id,
        config=config,
        package_name=config.get("packageName"),
    )

    if not connect_agent_bridge(bridge):
        return 1

    result = bridge.run()
    return 0 if result.get("success") else 1


class TaktikAgentRun:
    """One Taktik Agent session, from its config file."""

    def __init__(self, config: dict):
        self.config = config

    def run(self) -> int:
        return run_taktik_agent(self.config)
