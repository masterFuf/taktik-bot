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
import json
import os
import threading

# Bootstrap: UTF-8 + loguru + sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.runtime.signal_handler import setup_signal_handlers
from taktik.core.database import configure_db_service
from loguru import logger

from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.runtime.ipc import _ipc
from taktik.core.app.ai.providers.openrouter import AIService

# Graceful shutdown on SIGINT / SIGTERM
setup_signal_handlers()


def _build_agent_ai_service(*, api_key: str, ipc=None, vision_model: str = None, text_model: str = None):
    """Bridge-owned AI provider factory for the agent runtime."""
    return AIService(api_key=api_key, ipc=ipc, vision_model=vision_model, text_model=text_model)


class TaktikAgentBridge(InstagramBridgeBase):
    """Bridge that launches the autonomous TaktikAgentWorkflow."""

    def __init__(self, device_id: str, config: dict, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self.config = config

    def run(self):
        # Start stdin listener so Electron can request a graceful stop via {"command":"stop"}
        self._start_stdin_listener()

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
            ai_service_factory=_build_agent_ai_service,
        )
        # Expose workflow to signal handler so Ctrl+C triggers graceful stop
        from bridges.common.runtime import signal_handler as _sig
        _sig.update_workflow(workflow)

        result = workflow.run()
        logger.info(f"[TaktikAgentBridge] Session finished: {result}")
        return result

    def _start_stdin_listener(self):
        """Daemon thread: reads stdin for {"command":"stop"} and triggers workflow.stop()."""
        def _listen():
            try:
                for raw in sys.stdin:
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if msg.get("command") == "stop":
                            logger.info("[TaktikAgentBridge] Stop command received via stdin")
                            from bridges.common.runtime import signal_handler as _sig
                            if _sig._workflow and hasattr(_sig._workflow, "stop"):
                                _sig._workflow.stop()
                            break
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass  # stdin closed = Electron killed us (normal)

        t = threading.Thread(target=_listen, daemon=True, name="stdin-stop-listener")
        t.start()


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No config file provided"}), flush=True)
        sys.exit(1)

    config_path = sys.argv[1]

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"Failed to load config: {exc}"}), flush=True)
        sys.exit(1)

    device_id = config.get("deviceId")
    if not device_id:
        print(json.dumps({"success": False, "error": "No deviceId in config"}), flush=True)
        sys.exit(1)

    # Configure local SQLite database service
    try:
        configure_db_service()
        logger.info("[TaktikAgentBridge] Database service configured")
    except Exception as exc:
        logger.warning(f"[TaktikAgentBridge] Could not configure DB service: {exc}")

    # Connect to device
    bridge = TaktikAgentBridge(
        device_id=device_id,
        config=config,
        package_name=config.get("packageName"),
    )

    if not bridge.connect():
        print(json.dumps({"success": False, "error": "Failed to connect to device"}), flush=True)
        sys.exit(1)

    result = bridge.run()
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
