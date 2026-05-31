"""Workflow runner for the Instagram desktop automation bridge runtime."""

from __future__ import annotations

import json
from typing import Any

from bridges.instagram.runtime.ipc import (
    logger,
    send_error,
    send_log,
    send_message,
    send_stats,
    send_status,
)


class InstagramAutomationRunner:
    """Prepare and execute the core Instagram automation workflow."""

    def __init__(
        self,
        *,
        config: dict,
        device_manager: Any,
        app_service: Any,
        package_name: str | None,
        ai_enabled: bool,
        ai_service: Any | None,
        ai_config: dict,
        language: str,
    ):
        self.config = config
        self.device_manager = device_manager
        self.app_service = app_service
        self.package_name = package_name
        self.ai_enabled = ai_enabled
        self.ai_service = ai_service
        self.ai_config = ai_config
        self.language = language
        self.automation = None

    def build_workflow_config(self) -> dict:
        """Build the workflow configuration matching CLI format."""
        from taktik.core.social_media.instagram.workflows.core.config_builder import (
            build_instagram_automation_config,
        )

        return build_instagram_automation_config(self.config)

    def run(self) -> bool:
        """Run the configured workflow."""
        try:
            from taktik.core.social_media.instagram.workflows.core.automation import (
                InstagramAutomation,
            )

            workflow_config = self.build_workflow_config()

            target = self.config.get("target", "")
            workflow_type = self.config.get("workflowType")
            targets_display = ", @".join([t.strip() for t in target.split(",") if t.strip()])
            send_status("starting", f"Starting {workflow_type} workflow for @{targets_display}")
            send_log("info", f"Configuration: {json.dumps(workflow_config, indent=2)}")

            self._send_session_config()

            send_status("initializing", "Initializing automation...")
            self.automation = InstagramAutomation(self.device_manager)
            self._prepare_runtime(workflow_config)
            self._install_ai_hooks()

            send_status("running", "Running workflow...")
            self.automation.run_workflow()
            self._send_final_stats()

            send_status("completed", "Workflow completed successfully")
            return True

        except Exception as e:
            self._send_workflow_error(e)
            logger.exception("Workflow error")
            return False

    def _send_session_config(self) -> None:
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

    def _prepare_runtime(self, workflow_config: dict) -> None:
        from taktik.core.social_media.instagram.workflows.core.runtime_setup import (
            prepare_instagram_automation_runtime,
        )

        prepare_instagram_automation_runtime(
            automation=self.automation,
            workflow_config=workflow_config,
            package_name=self.package_name,
            installed_version_provider=(
                self.app_service.get_installed_version if self.app_service else None
            ),
            log=send_log,
        )

    def _install_ai_hooks(self) -> None:
        if not (self.ai_enabled and self.ai_service):
            return

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

    def _send_final_stats(self) -> None:
        stats = self.automation.stats
        send_stats(
            likes=stats.get("likes", 0),
            follows=stats.get("follows", 0),
            comments=stats.get("comments", 0),
            profiles=stats.get("interactions", 0),
            unfollows=stats.get("unfollows", 0),
        )

    @staticmethod
    def _send_workflow_error(error: Exception) -> None:
        error_msg = str(error)
        if "uiautomator" in error_msg.lower() or "atx" in error_msg.lower():
            send_error(
                f"UIAutomator2 crashed during workflow: {error_msg}",
                error_code="ATX_AGENT_CRASHED",
            )
        elif "timeout" in error_msg.lower():
            send_error(f"Workflow timed out: {error_msg}", error_code="WORKFLOW_TIMEOUT")
        else:
            send_error(f"Workflow error: {error_msg}", error_code="WORKFLOW_ERROR")
