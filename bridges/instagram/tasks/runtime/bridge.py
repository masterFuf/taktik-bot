"""Instagram task bridge runtime.

The bridge adapts a payload and emits events; the task itself lives behind the Agent
registry. Resolving through the registry rather than importing task modules here is the
point of the family: a task registered once is reachable from the CLI, the scheduler and
this bridge, and adding one never means editing a dispatch table in three places.

Config contract (JSON file passed as argv[1]):
    deviceId     device serial (required)
    taskId       short task name ("story_relay") or full id ("instagram.task.story_relay")
    params       dict handed to the task handler as its payload
    packageName  optional Instagram package override (clones)
"""

from __future__ import annotations

import signal

from bridges.common.device.app_manager import AppService
from bridges.common.device.connection import ConnectionService
from bridges.common.runtime.signal_handler import setup_signal_handlers
from bridges.instagram.runtime.ipc import _ipc, send_error, send_message, send_status

TASK_ID_PREFIX = "instagram.task."


class TaskBridge:
    """Run one `instagram.task.*` one-shot on a prepared device."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self.task_id = self._canonical_task_id(config.get("taskId"))
        self.params = config.get("params") or {}
        self.package_name = config.get("packageName")
        self._connection = None

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    @staticmethod
    def _canonical_task_id(raw) -> str | None:
        """Accept the short name or the full id — the registry only knows the full one."""
        if not raw or not isinstance(raw, str):
            return None
        return raw if raw.startswith(TASK_ID_PREFIX) else f"{TASK_ID_PREFIX}{raw}"

    def _shutdown(self, signum, frame):
        send_status("stopping", "Received shutdown signal")

    def run(self) -> int:
        if not self.device_id:
            send_error("Device ID is required")
            return 1
        if not self.task_id:
            send_error("taskId is required (e.g. 'story_relay')")
            return 1

        device = self._prepare_runtime_session()
        if device is None:
            return 1

        return self._run_task(device)

    def _prepare_runtime_session(self):
        """DB, device connection, clean Instagram restart — same order as every bridge."""
        try:
            from taktik.core.database import configure_db_service

            configure_db_service()
        except Exception as e:  # noqa: BLE001
            send_error(f"Database setup failed: {e}")
            return None

        send_status("connecting", f"Connecting to device {self.device_id}...")
        self._connection = ConnectionService(self.device_id)
        if not self._connection.connect():
            send_error(f"Failed to connect to device {self.device_id}")
            return None

        device = self._connection.device
        if not device:
            send_error("Device object unavailable after connection")
            return None

        app_service = AppService(
            self._connection,
            platform="instagram",
            package_override=self.package_name,
        )
        # Clean restart, always: a task starts from a known screen (the feed), never from
        # wherever a previous run left the app — e.g. a fullscreen story viewer.
        send_status("initializing", "Restarting Instagram...")
        app_service.restart()

        return device

    def _run_task(self, device) -> int:
        from taktik.core.agent.kernel.contracts import WorkflowInvocation
        from taktik.core.agent.kernel.registry import WorkflowRegistry
        from taktik.core.social_media.instagram.workflows.tasks import (
            register_instagram_task_handlers,
        )

        registry = WorkflowRegistry()
        register_instagram_task_handlers(registry, device=device, device_id=self.device_id)

        if not registry.contains(self.task_id):
            send_error(
                f"Unknown task '{self.task_id}' — registered: {', '.join(registry.workflow_ids())}"
            )
            return 1

        send_status("running", f"Running {self.task_id}...")
        try:
            handler = registry.resolve(self.task_id)
            # Params travel as the payload; the invocation carries none so the handler's
            # merge cannot apply them twice.
            invocation = WorkflowInvocation(platform="instagram", workflow_id=self.task_id)
            report = handler(invocation, dict(self.params))
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Task error: {exc}")
            send_message("log", level="error", message=traceback.format_exc())
            return 1

        success = bool(report.get("success")) if isinstance(report, dict) else bool(report)
        send_status("success" if success else "error",
                    (report or {}).get("reason") or "" if isinstance(report, dict) else "")
        send_message(
            "task_result",
            success=success,
            taskId=self.task_id,
            report=report if isinstance(report, dict) else {"value": report},
        )
        return 0 if success else 1


__all__ = ["TaskBridge"]
