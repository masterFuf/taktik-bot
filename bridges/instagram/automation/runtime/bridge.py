"""Instagram desktop automation bridge runtime class.

The run is `run_instagram_automation`, the launcher the Agent handlers `instagram.automation.*`
(and so the CLI) call too. Called by name rather than through the registry so the app's config
contract test can follow the payload. The bridge keeps what belongs to the desktop process: the
database setup, its device connection, the IP rotation, the media capture, the decision round
trip, its stdout, and the app stop when the process ends.
"""

from __future__ import annotations

from bridges.instagram.runtime.ai import create_instagram_ai_service
from bridges.instagram.automation.runtime.decision_client import DesktopProfileDecisionClient
from bridges.instagram.automation.runtime.events import (
    InstagramAutomationReporter,
    send_instagram_workflow_error,
)
from bridges.instagram.automation.runtime.media_capture import InstagramMediaCaptureRuntime
from bridges.instagram.automation.runtime.session import InstagramDesktopRuntime
from bridges.instagram.automation.runtime.signals import register_desktop_shutdown_handlers
from bridges.instagram.automation.runtime.validation import (
    format_targets_display,
    validate_desktop_bridge_config,
)
from bridges.instagram.runtime.ipc import _ipc, logger, send_log, send_status


class DesktopBridge:
    """Bridge between Desktop app and TAKTIK Bot."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self.workflow_type = config.get("workflowType")
        self.target = config.get("target")
        self.package_name = config.get("packageName")
        self.running = True
        self.runtime = InstagramDesktopRuntime(
            device_id=self.device_id,
            package_name=self.package_name,
            network_reset=config.get("networkReset", {}),
        )

        self.ai_config = config.get("ai", {})
        self.ai_enabled, self.ai_service = create_instagram_ai_service(
            ai_config=self.ai_config,
            ipc=_ipc,
            log=send_log,
        )
        decision_config = self.ai_config.get("decision") or {}
        self.decision_client = (
            DesktopProfileDecisionClient(ipc=_ipc, log=send_log)
            if decision_config.get("mode") == "decide"
            else None
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
        if self.decision_client:
            self.decision_client.close()

    def close(self) -> None:
        """Release bridge-owned background readers before interpreter shutdown."""
        if self.decision_client:
            self.decision_client.close()

    def _start_instagram(self, _package_name) -> bool:
        # The app service was built on the payload's package when the device connected.
        return self.runtime.launch_instagram()

    def _ai_service_for(self, _ai_config):
        # Built with the bridge, before the run, as the desktop has always seen it announced.
        return self.ai_service if self.ai_enabled else None

    def run_workflow(self) -> dict:
        """Start Instagram and run the configured workflow (the core launcher)."""
        from taktik.core.social_media.instagram.workflows.core.agent_handler import (
            run_instagram_automation,
        )

        app_service = self.runtime.app_service
        return run_instagram_automation(
            self.config,
            device_manager=self.runtime.device_manager,
            instagram_start=self._start_instagram,
            instagram_ai_service=self._ai_service_for,
            decision_provider=self.decision_client.request_plan if self.decision_client else None,
            instagram_installed_version=app_service.get_installed_version if app_service else None,
            reporter=InstagramAutomationReporter(self.config, ai_enabled=self.ai_enabled),
            log=send_log,
        )

    def run(self) -> int:
        """Main entry point."""
        try:
            return self._run()
        finally:
            self.close()

    def _run(self) -> int:
        from taktik.core.social_media.instagram.workflows.core.agent_handler import InstagramStartError

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

        # Before anything opens Instagram: if a fresh IP was requested and did not happen, stop here
        # rather than run the account on the previous account's IP.
        if not self.runtime.reset_network_if_enabled(_ipc):
            return 6

        self.media_capture.start()

        started = True
        try:
            self.run_workflow()
        except InstagramStartError:
            started = False
            self.media_capture.stop()
            return 4
        except Exception as e:
            send_instagram_workflow_error(e)
            logger.exception("Workflow error")
            return 5
        finally:
            if started:
                self.media_capture.stop()
                self.runtime.stop_app()

        send_status("finished", "Session completed")
        return 0


__all__ = ["DesktopBridge"]
