#!/usr/bin/env python3
"""
Desktop Bridge for TAKTIK Bot
This script allows the TAKTIK Desktop app to launch bot sessions programmatically.
It accepts a JSON configuration and runs the appropriate workflow.
"""

import sys
import os
import json
import signal
import logging

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.instagram.automation.runtime.ai import create_instagram_ai_service
from bridges.instagram.automation.runtime.input import load_desktop_config
from bridges.instagram.automation.runtime.media_capture import InstagramMediaCaptureRuntime
from bridges.instagram.automation.runtime.session import InstagramDesktopRuntime
from bridges.instagram.automation.runtime.validation import (
    format_targets_display,
    validate_desktop_bridge_config,
)
from bridges.instagram.automation.runtime.workflow import InstagramAutomationRunner
from bridges.instagram.runtime.ipc import (
    logger, _ipc,
    send_status, send_error, send_log,
    setup_stats_callback,
)
from bridges.instagram.diagnostics.debug import DebugBridge

# Configure logging for desktop integration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class DesktopBridge:
    """Bridge between Desktop app and TAKTIK Bot."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get('deviceId')
        self.workflow_type = config.get('workflowType')
        self.target = config.get('target')
        self.language = config.get('language', 'en')
        self.package_name = config.get('packageName')  # Clone package (e.g. com.instagram.android.c1)
        self.running = True
        self.runtime = InstagramDesktopRuntime(
            device_id=self.device_id,
            package_name=self.package_name,
            network_reset=config.get('networkReset', {}),
        )
        self.automation = None

        # AI mode configuration
        self.ai_config = config.get('ai', {})
        self.ai_enabled, self.ai_service = create_instagram_ai_service(
            ai_config=self.ai_config,
            ipc=_ipc,
            log=send_log,
        )

        # Media capture service
        self.media_capture = InstagramMediaCaptureRuntime(
            device_id=self.device_id,
            enabled=config.get('mediaCaptureEnabled', False),
        )

        # Setup signal handlers for graceful shutdown
        from bridges.common.runtime.signal_handler import setup_signal_handlers
        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signal."""
        send_status("stopping", "Received shutdown signal")
        self.running = False

    def run_workflow(self) -> bool:
        """Run the configured workflow."""
        runner = InstagramAutomationRunner(
            config=self.config,
            device_manager=self.runtime.device_manager,
            app_service=self.runtime.app_service,
            package_name=self.package_name,
            ai_enabled=self.ai_enabled,
            ai_service=self.ai_service,
            ai_config=self.ai_config,
            language=self.language,
        )
        result = runner.run()
        self.automation = runner.automation
        return result

    def run(self) -> int:
        """Main entry point."""
        send_status("starting", "TAKTIK Desktop Bridge starting...")
        targets_display, target_count = format_targets_display(self.target)
        send_log("info", f"Config: device={self.device_id}, workflow={self.workflow_type}, targets=[{targets_display}] ({target_count} target(s))")

        # Validate configuration
        if not validate_desktop_bridge_config(
            device_id=self.device_id,
            workflow_type=self.workflow_type,
            target=self.target,
        ):
            return 1

        # Setup license
        if not self.runtime.setup_database():
            return 2

        # Connect to device
        if not self.runtime.connect_device():
            return 3

        # Network reset (get new IP before session)
        self.runtime.reset_network_if_enabled(_ipc)

        # Start media capture (non-blocking if fails)
        self.media_capture.start()

        # Launch Instagram
        if not self.runtime.launch_instagram():
            self.media_capture.stop()
            return 4

        # Run workflow
        try:
            if not self.run_workflow():
                self.media_capture.stop()
                return 5
        finally:
            # Always stop media capture and close Instagram app
            self.media_capture.stop()
            self.runtime.stop_app()

        send_status("finished", "Session completed")
        return 0


def main():
    """Main entry point."""
    try:
        # Setup stats IPC callback before any workflow runs
        setup_stats_callback()
        config = load_desktop_config(send_log)

        if config is None:
            send_error("No configuration provided. Use: desktop_bridge <config.json> or pipe JSON to stdin")
            sys.exit(1)

        # Check if this is a debug command via JSON config
        if config.get('debugMode'):
            bridge = DebugBridge(config)
            exit_code = bridge.run()
            sys.exit(exit_code)

        # Create and run bridge
        bridge = DesktopBridge(config)
        exit_code = bridge.run()

        sys.exit(exit_code)

    except json.JSONDecodeError as e:
        send_error(f"Invalid JSON configuration: {str(e)}")
        sys.exit(1)
    except Exception as e:
        send_error(f"Bridge error: {str(e)}")
        logger.exception("Bridge error")
        sys.exit(1)


if __name__ == "__main__":
    main()
