#!/usr/bin/env python3
"""
Taktik Agent Bridge for TAKTIK Desktop.

Entry point launched by the Electron app for the autonomous Taktik Agent session.
Reads a JSON config from sys.argv[1], connects to the Android device, and runs
the core Taktik Agent workflow.
"""

import os
import sys

# Bootstrap: UTF-8 + loguru + sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.runtime.signal_handler import setup_signal_handlers
from loguru import logger

from bridges.instagram.agent.runtime.commands import load_agent_bridge_config
from bridges.instagram.agent.runtime.session import (
    configure_agent_database,
    connect_agent_bridge,
)
from bridges.instagram.agent.runtime.stop_listener import start_agent_stop_listener
from bridges.instagram.agent.runtime.workflow import run_agent_workflow
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.runtime.ipc import _ipc

# Graceful shutdown on SIGINT / SIGTERM
setup_signal_handlers()


class TaktikAgentBridge(InstagramBridgeBase):
    """Bridge that launches the autonomous Taktik Agent workflow."""

    def __init__(self, device_id: str, config: dict, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self.config = config

    def run(self):
        # Electron can request a graceful stop via stdin: {"command":"stop"}.
        start_agent_stop_listener()
        result = run_agent_workflow(
            app=self._app,
            device_manager=self.device_manager,
            config=self.config,
            ipc=_ipc,
        )
        logger.info(f"[TaktikAgentBridge] Session finished: {result}")
        return result


def main():
    config = load_agent_bridge_config(sys.argv)
    if config is None:
        sys.exit(1)

    device_id = config.get("deviceId")
    configure_agent_database()

    bridge = TaktikAgentBridge(
        device_id=device_id,
        config=config,
        package_name=config.get("packageName"),
    )

    if not connect_agent_bridge(bridge):
        sys.exit(1)

    result = bridge.run()
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
