"""Debug commands exposed through the Instagram desktop bridge."""

from __future__ import annotations

from bridges.common.entrypoint import send_run_error
from bridges.instagram.common.ipc import send_error, send_log
from bridges.instagram.automation.debug_actions import (
    analyze_current_screen,
    connect_debug_device,
    detect_problematic_pages,
)


class DebugBridge:
    """Run debug commands used by Electron's debug tooling."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self.mode = config.get("mode", "analyze")

    def run(self) -> int:
        """Run debug command."""
        try:
            send_log("debug", f"Starting debug command: mode={self.mode}, device={self.device_id}")

            if not self.device_id:
                send_error("Device ID is required")
                return 1

            device = connect_debug_device(self.device_id)
            if device is None:
                return 2

            if self.mode == "analyze":
                return analyze_current_screen(device)
            if self.mode == "detect":
                return detect_problematic_pages(device)

            send_error(f"Unknown debug mode: {self.mode}")
            return 3

        except Exception as e:
            # An import that failed is said with its code by `send_run_error`, whatever the words.
            send_run_error(f"Debug error: {e}", e)
            return 1
