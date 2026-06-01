"""Instagram desktop automation bridge runtime class."""

from __future__ import annotations

from bridges.instagram.automation.runtime.ai import create_instagram_ai_service
from bridges.instagram.automation.runtime.media_capture import InstagramMediaCaptureRuntime
from bridges.instagram.automation.runtime.session import InstagramDesktopRuntime
from bridges.instagram.automation.runtime.signals import register_desktop_shutdown_handlers
from bridges.instagram.automation.runtime.validation import (
    format_targets_display,
    validate_desktop_bridge_config,
)
from bridges.instagram.automation.runtime.workflow import InstagramAutomationRunner
from bridges.instagram.runtime.ipc import _ipc, send_log, send_status


class DesktopBridge:
    """Bridge between Desktop app and TAKTIK Bot."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self.workflow_type = config.get("workflowType")
        self.target = config.get("target")
        self.language = config.get("language", "en")
        self.package_name = config.get("packageName")
        self.running = True
        self.runtime = InstagramDesktopRuntime(
            device_id=self.device_id,
            package_name=self.package_name,
            network_reset=config.get("networkReset", {}),
        )
        self.automation = None

        self.ai_config = config.get("ai", {})
        self.ai_enabled, self.ai_service = create_instagram_ai_service(
            ai_config=self.ai_config,
            ipc=_ipc,
            log=send_log,
        )

        self.media_capture = InstagramMediaCaptureRuntime(
            device_id=self.device_id,
            enabled=config.get("mediaCaptureEnabled", False),
        )

        register_desktop_shutdown_handlers(self._handle_shutdown, ipc=_ipc)

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
        send_log(
            "info",
            (
                f"Config: device={self.device_id}, workflow={self.workflow_type}, "
                f"targets=[{targets_display}] ({target_count} target(s))"
            ),
        )

        if not validate_desktop_bridge_config(
            device_id=self.device_id,
            workflow_type=self.workflow_type,
            target=self.target,
        ):
            return 1

        if not self.runtime.setup_database():
            return 2

        if not self.runtime.connect_device():
            return 3

        self.runtime.reset_network_if_enabled(_ipc)
        self.media_capture.start()

        if not self.runtime.launch_instagram():
            self.media_capture.stop()
            return 4

        try:
            if not self.run_workflow():
                self.media_capture.stop()
                return 5
        finally:
            self.media_capture.stop()
            self.runtime.stop_app()

        send_status("finished", "Session completed")
        return 0


__all__ = ["DesktopBridge"]
