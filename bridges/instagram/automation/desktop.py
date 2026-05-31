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

from bridges.common.device.connection import ConnectionService
from bridges.common.device.app_manager import AppService
from bridges.instagram.automation.input import load_desktop_config
from bridges.instagram.automation.media_capture import InstagramMediaCaptureRuntime
from bridges.instagram.base import (
    logger, _ipc,
    send_message, send_status, send_stats,
    send_error, send_log,
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
        self.limits = config.get('limits', {})
        self.probabilities = config.get('probabilities', {})
        self.filters = config.get('filters', {})
        self.session_config = config.get('session', {})
        self.comments_config = config.get('comments', {})
        self.feed_stories_config = config.get('feedStories', {})
        self.unfollow_config = config.get('unfollow', {})  # Unfollow specific settings
        self.language = config.get('language', 'en')
        self.package_name = config.get('packageName')  # Clone package (e.g. com.instagram.android.c1)
        self.running = True
        # Shared services
        self._connection = ConnectionService(self.device_id) if self.device_id else None
        self._app = None  # initialized after connect
        self.device_manager = None  # backward-compatible alias
        self.automation = None

        # AI mode configuration
        self.ai_config = config.get('ai', {})
        self.ai_enabled = self.ai_config.get('enabled', False)
        self.ai_service = None

        # Network reset configuration
        self.network_reset_config = config.get('networkReset', {})
        self.network_reset_enabled = self.network_reset_config.get('enabled', False)
        self.network_reset_method = self.network_reset_config.get('method', 'data')  # 'data' or 'airplane'
        if self.ai_enabled:
            api_key = self.ai_config.get('openrouterApiKey', '')
            if api_key and len(api_key) > 5:
                from taktik.core.app.ai.providers.openrouter import AIService
                vision_model = self.ai_config.get('visionModel') or None
                self.ai_service = AIService(api_key=api_key, ipc=_ipc, vision_model=vision_model)
                send_log("info", "ðŸ¤– AI mode enabled â€” Smart Comments / Profile Analysis / Post Analysis")
            else:
                send_log("warning", "AI mode requested but no OpenRouter API key provided")
                self.ai_enabled = False

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

    def validate_config(self) -> bool:
        """Validate the configuration."""
        if not self.device_id:
            send_error("Device ID is required")
            return False
        if not self.workflow_type:
            send_error("Workflow type is required")
            return False
        if not self.target:
            send_error("Target is required")
            return False
        return True

    def setup_license(self) -> bool:
        """Setup database service for the bot process."""
        try:
            send_status("initializing", "Setting up database service...")

            # Configure local database service (SQLite)
            from taktik.core.database import configure_db_service
            configure_db_service()

            send_status("license_valid", "Database service configured")
            return True

        except Exception as e:
            send_error(f"Database setup failed: {str(e)}", error_code="LICENSE_SETUP_FAILED")
            logger.exception("Database setup failed")
            return False

    def connect_device(self) -> bool:
        """Connect to the specified device using ConnectionService."""
        try:
            send_status("connecting", f"Connecting to device {self.device_id}...")

            if not self._connection:
                self._connection = ConnectionService(self.device_id)

            if not self._connection.connect():
                send_error(f"Failed to connect to device {self.device_id}", error_code="DEVICE_CONNECTION_FAILED")
                return False

            # Backward-compatible alias
            self.device_manager = self._connection.device_manager
            self._app = AppService(self._connection, platform="instagram", package_override=self.package_name)

            send_status("connected", f"Connected to {self.device_id}")
            return True

        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                send_error(f"Device connection timed out: {error_msg}", error_code="DEVICE_CONNECTION_TIMEOUT")
            else:
                send_error(f"Failed to connect to device: {error_msg}", error_code="DEVICE_CONNECTION_FAILED")
            logger.exception("Device connection failed")
            return False

    def launch_instagram(self) -> bool:
        """Launch Instagram on the device using ConnectionService + AppService."""
        try:
            send_status("launching", "Launching Instagram...")

            # Check ATX health via ConnectionService (non-blocking)
            atx_result = self._connection.check_atx_health(repair=True, max_retries=3)
            if not atx_result["atx_healthy"]:
                error_detail = atx_result.get("error", "Unknown")
                if atx_result.get("repaired"):
                    send_status("atx_repaired", "UIAutomator2 agent repaired successfully")
                else:
                    logger.warning(f"ATX repair failed: {error_detail} - continuing anyway")
                    send_log("warning", f"ATX repair failed ({error_detail}) but continuing - workflow may still work")

            # Check Instagram is installed
            if not self._app.is_installed():
                send_error("Instagram is not installed on this device", error_code="INSTAGRAM_NOT_INSTALLED")
                return False

            # Launch Instagram
            if not self._app.launch():
                send_error("Failed to launch Instagram", error_code="INSTAGRAM_LAUNCH_FAILED")
                return False

            send_status("instagram_ready", "Instagram launched successfully")
            return True

        except Exception as e:
            error_msg = str(e)
            if "uiautomator" in error_msg.lower() or "atx" in error_msg.lower():
                send_error(f"UIAutomator2 connection failed: {error_msg}", error_code="ATX_AGENT_FAILED")
            else:
                send_error(f"Failed to launch Instagram: {error_msg}", error_code="INSTAGRAM_LAUNCH_FAILED")
            logger.exception("Instagram launch failed")
            return False

    def build_workflow_config(self) -> dict:
        """Build the workflow configuration matching CLI format."""
        from taktik.core.social_media.instagram.workflows.core.config_builder import (
            build_instagram_automation_config,
        )

        return build_instagram_automation_config(self.config)

    def run_workflow(self) -> bool:
        """Run the configured workflow."""
        try:
            from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation

            workflow_config = self.build_workflow_config()

            # Parse targets for display
            targets_display = ', @'.join([t.strip() for t in self.target.split(',') if t.strip()])
            send_status("starting", f"Starting {self.workflow_type} workflow for @{targets_display}")
            send_log("info", f"Configuration: {json.dumps(workflow_config, indent=2)}")

            from taktik.core.social_media.instagram.workflows.core.config_builder import (
                build_instagram_session_config_event,
            )

            send_message(
                "session_config",
                config=build_instagram_session_config_event(
                    self.config,
                    ai_enabled=self.ai_enabled,
                ),
            )

            # Create automation instance (matching CLI usage)
            send_status("initializing", "Initializing automation...")
            self.automation = InstagramAutomation(self.device_manager)

            from taktik.core.social_media.instagram.workflows.core.runtime_setup import (
                prepare_instagram_automation_runtime,
            )

            prepare_instagram_automation_runtime(
                automation=self.automation,
                workflow_config=workflow_config,
                package_name=self.package_name,
                installed_version_provider=(
                    self._app.get_installed_version if self._app else None
                ),
                log=send_log,
            )

            # â”€â”€ AI hooks (monkey-patch interaction engine if AI mode is ON) â”€â”€
            if self.ai_enabled and self.ai_service:
                from taktik.core.social_media.instagram.workflows.core.ai_hooks import (
                    install_instagram_ai_hooks,
                )

                install_instagram_ai_hooks(
                    ai=self.ai_service,
                    ai_config=self.ai_config,
                    device=self.device_manager.device if self.device_manager else None,
                    language=self.language,
                    log=send_log,
                )

            # Run the workflow
            send_status("running", "Running workflow...")
            self.automation.run_workflow()

            # Get final stats
            stats = self.automation.stats
            send_stats(
                likes=stats.get('likes', 0),
                follows=stats.get('follows', 0),
                comments=stats.get('comments', 0),
                profiles=stats.get('interactions', 0),
                unfollows=stats.get('unfollows', 0)
            )

            send_status("completed", "Workflow completed successfully")
            return True

        except Exception as e:
            error_msg = str(e)
            if "uiautomator" in error_msg.lower() or "atx" in error_msg.lower():
                send_error(f"UIAutomator2 crashed during workflow: {error_msg}", error_code="ATX_AGENT_CRASHED")
            elif "timeout" in error_msg.lower():
                send_error(f"Workflow timed out: {error_msg}", error_code="WORKFLOW_TIMEOUT")
            else:
                send_error(f"Workflow error: {error_msg}", error_code="WORKFLOW_ERROR")
            logger.exception("Workflow error")
            return False

    def run(self) -> int:
        """Main entry point."""
        send_status("starting", "TAKTIK Desktop Bridge starting...")
        # Parse targets for display
        target_list = [t.strip() for t in self.target.split(',') if t.strip()]
        targets_display = ', '.join(target_list)
        send_log("info", f"Config: device={self.device_id}, workflow={self.workflow_type}, targets=[{targets_display}] ({len(target_list)} target(s))")

        # Validate configuration
        if not self.validate_config():
            return 1

        # Setup license
        if not self.setup_license():
            return 2

        # Connect to device
        if not self.connect_device():
            return 3

        # Network reset (get new IP before session)
        if self.network_reset_enabled:
            from bridges.common.device.network import perform_network_reset
            perform_network_reset(self.device_id, method=self.network_reset_method, ipc=_ipc)

        # Start media capture (non-blocking if fails)
        self.media_capture.start()

        # Launch Instagram
        if not self.launch_instagram():
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
            if self._app:
                try:
                    self._app.stop()
                except Exception:
                    pass

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
