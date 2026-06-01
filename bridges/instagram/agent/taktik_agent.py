#!/usr/bin/env python3
"""
Taktik Agent Bridge for TAKTIK Desktop.

Entry point launched by the Electron app for the autonomous Taktik Agent session.
Reads a JSON config from sys.argv[1], connects to the Android device, and runs
the TaktikAgentWorkflow which behaves like a human browsing Instagram.

Config keys:
  deviceId            (str, required)
  packageName         (str, optional)  — clone package e.g. "com.taktik.ig1"
  openrouter_api_key  (str, required)  — API key for AI vision calls
  session_duration_min (int)           — default 25
  max_likes           (int)            — default 80
  max_comments        (int)            — default 15
  max_follows         (int)            — default 20
  max_profile_visits  (int)            — default 40
  skip_reels          (bool)           — default true
"""

import sys
import os

# Bootstrap: UTF-8 + loguru + sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.runtime.signal_handler import setup_signal_handlers
from loguru import logger

from bridges.instagram.agent.runtime.ai import build_agent_ai_service
from bridges.instagram.agent.runtime.commands import load_agent_bridge_config
from bridges.instagram.agent.runtime.session import (
    configure_agent_database,
    connect_agent_bridge,
)
from bridges.instagram.agent.runtime.stop_listener import start_agent_stop_listener
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.runtime.ipc import _ipc

# Graceful shutdown on SIGINT / SIGTERM
setup_signal_handlers()


class TaktikAgentBridge(InstagramBridgeBase):
    """Bridge that launches the autonomous TaktikAgentWorkflow."""

    def __init__(self, device_id: str, config: dict, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self.config = config

    def run(self):
        # Start stdin listener so Electron can request a graceful stop via {"command":"stop"}
        start_agent_stop_listener()

        # Launch Instagram before starting the workflow
        _ipc.status("launching", "Launching Instagram…")
        if not self._app.launch():
            _ipc.error("Failed to launch Instagram", error_code="INSTAGRAM_LAUNCH_FAILED")
            return {"success": False, "error": "Failed to launch Instagram"}
        _ipc.status("instagram_ready", "Instagram launched successfully")

        from taktik.core.agent.scenarios.instagram_feed_autopilot import TaktikAgentWorkflow
        workflow = TaktikAgentWorkflow(
            device_manager=self.device_manager,
            config=self.config,
            ipc=_ipc,
            ai_service_factory=build_agent_ai_service,
        )
        # Expose workflow to signal handler so Ctrl+C triggers graceful stop
        from bridges.common.runtime import signal_handler as _sig
        _sig.update_workflow(workflow)

        result = workflow.run()
        logger.info(f"[TaktikAgentBridge] Session finished: {result}")
        return result


def main():
    config = load_agent_bridge_config(sys.argv)
    if config is None:
        sys.exit(1)

    device_id = config.get("deviceId")
    configure_agent_database()

    # Connect to device
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
