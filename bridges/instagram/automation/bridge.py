"""Instagram desktop automation bridge runtime class.

The run is `run_instagram_automation`, the launcher the Agent handlers `instagram.automation.*`
(and so the CLI) call too. Called by name rather than through the registry so the app's config
contract test can follow the payload. The bridge keeps what belongs to the desktop process: the
database setup, its device connection, the IP rotation, the media capture, the decision round
trip, its stdout, and the app stop when the process ends.

The launcher reads and validates the payload, then calls the bridge's `connect`: the database
setup, the connection, the IP rotation and the media capture happen there, after the reading. A
payload the reader refuses ends on the run's error line (`Workflow error: ...`, `WORKFLOW_ERROR`,
exit 1) with nothing connected, rotated or stopped. A phone the launcher's network door refuses ends
on `NETWORK_UNREACHABLE`, exit 6.
"""

from __future__ import annotations

from bridges.instagram.common.ai import create_instagram_ai_service
from bridges.instagram.automation.decision_client import DesktopProfileDecisionClient
from bridges.instagram.automation.events import (
    InstagramAutomationReporter,
    send_instagram_run_error,
    send_instagram_workflow_error,
)
from bridges.instagram.automation.media_capture import InstagramMediaCaptureRuntime
from bridges.instagram.automation.session import InstagramDesktopRuntime
from bridges.instagram.automation.signals import register_desktop_shutdown_handlers
from bridges.instagram.automation.validation import (
    format_targets_display,
    validate_desktop_bridge_config,
)
from bridges.instagram.common.ipc import _ipc, logger, send_log, send_status


class _PhoneNotReady(Exception):
    """The bridge could not prepare the phone the launcher asked for; the step that failed has
    already said why on stdout. `exit_code` is the bridge's exit code for that step."""

    def __init__(self, exit_code: int):
        super().__init__(f"phone not ready (exit {exit_code})")
        self.exit_code = exit_code


class DesktopBridge:
    """Bridge between Desktop app and TAKTIK Bot."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self.workflow_type = config.get("workflowType")
        self.target = config.get("target")
        self.package_name = config.get("packageName")
        self.running = True
        # Set when the launcher asks for the phone, and once the phone is ready for the run.
        self.phone_asked = False
        self.phone_ready = False
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

    def _connect(self, _package_name):
        """The phone the launcher asks for, once it has read the payload: the database setup, the
        connection (its app service is built on the payload's package), the IP rotation, then the
        media capture."""
        from taktik.core.social_media.instagram.workflows.common.startup import InstagramRunPhone

        self.phone_asked = True
        if not self.runtime.setup_database():
            raise _PhoneNotReady(2)
        if not self.runtime.connect_device():
            raise _PhoneNotReady(3)
        # Before anything opens Instagram: if a fresh IP was requested and did not happen, stop here
        # rather than run the account on the previous account's IP.
        if not self.runtime.reset_network_if_enabled(_ipc):
            raise _PhoneNotReady(6)
        self.media_capture.start()
        self.phone_ready = True

        app_service = self.runtime.app_service
        return InstagramRunPhone(
            device_manager=self.runtime.device_manager,
            start=self.runtime.launch_instagram,
            installed_version=app_service.get_installed_version if app_service else None,
        )

    def _ai_service_for(self, _ai_config):
        # Built with the bridge, before the run, as the desktop has always seen it announced.
        return self.ai_service if self.ai_enabled else None

    def run_workflow(self) -> dict:
        """Run the configured workflow (the core launcher), on the phone `_connect` prepares."""
        from taktik.core.social_media.instagram.workflows.automation.agent_handler import (
            run_instagram_automation,
        )

        return run_instagram_automation(
            self.config,
            connect=self._connect,
            instagram_ai_service=self._ai_service_for,
            decision_provider=self.decision_client.request_plan if self.decision_client else None,
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
        from bridges.common.network import send_network_refusal
        from taktik.core.shared.device.network_door import NetworkUnreachableError
        from taktik.core.social_media.instagram.workflows.common.startup import InstagramStartError

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

        # The app is stopped at the end of a run on a ready phone, unless Instagram never started.
        stop_at_end = True
        try:
            self.run_workflow()
        except _PhoneNotReady as not_ready:
            return not_ready.exit_code
        except NetworkUnreachableError as refused:
            # The launcher's network door: the same exit as a refusal at the IP rotation.
            send_network_refusal(refused, "Session")
            return 6
        except InstagramStartError:
            stop_at_end = False
            self.media_capture.stop()
            return 4
        except Exception as e:
            if isinstance(e, ValueError) and not self.phone_asked:
                # The launcher's reader refused the payload: nothing touched the phone, no traceback.
                send_instagram_run_error(str(e))
                logger.warning(f"Payload refused before the phone was touched: {e}")
                return 1
            send_instagram_workflow_error(e)
            logger.exception("Workflow error")
            return 5
        finally:
            if stop_at_end and self.phone_ready:
                self.media_capture.stop()
                self.runtime.stop_app()

        send_status("finished", "Session completed")
        return 0


__all__ = ["DesktopBridge"]
