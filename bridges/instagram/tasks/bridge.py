"""Instagram task bridge runtime.

The bridge adapts a payload and emits events; the task itself lives behind the Agent
registry. Resolving through the registry rather than importing task modules here is the
point of the family: a task registered once is reachable from the CLI, the scheduler and
this bridge, and adding one never means editing a dispatch table in three places.

Config contract (JSON file passed as argv[1]):
    deviceId     device serial (required)
    taskId       short task name ("story_relay") or full id ("instagram.task.story_relay")
    params       dict handed to the task handler as its payload, `packageName` (a clone) included:
                 the task's launcher reads it and asks this bridge for the phone on that Instagram
"""

from __future__ import annotations

import signal

from taktik.core.shared.device.app_manager import AppService
from bridges.common.entrypoint import send_run_error
from bridges.common.network import send_run_refusal
from bridges.common.run_setup import connect_run_device
from bridges.common.signal_handler import setup_signal_handlers
from bridges.instagram.common.ipc import _ipc, send_error, send_message, send_status
from taktik.core.shared.diagnostics.run_halt import RunRefused
from taktik.core.social_media.instagram.workflows.common.startup import InstagramRunPhone

TASK_ID_PREFIX = "instagram.task."


class TaskBridge:
    """Run one `instagram.task.*` one-shot on a prepared device."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self.task_id = self._canonical_task_id(config.get("taskId"))
        self.params = config.get("params") or {}
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

        if self._prepare_runtime_session() is None:
            return 1

        return self._run_task()

    def _prepare_runtime_session(self):
        """DB, then device connection — same order as every bridge; the task's launcher asks for
        the phone on its Instagram (`_run_phone`)."""
        self._connection = connect_run_device(self.device_id)
        return self._connection.device if self._connection is not None else None

    def _run_phone(self, package_name: str | None) -> InstagramRunPhone:
        """The phone the launcher asks for, on the Instagram it read (a clone; None: the installed
        one): its clean restart, always (a task starts from a known screen, the feed, never from
        wherever a previous run left the app, e.g. a fullscreen story viewer), and its installed
        version, for the selectors."""
        connection = self._connection
        if connection is None:
            raise RuntimeError("The task asked for the phone before the bridge connected it")
        app_service = AppService(
            connection,
            platform="instagram",
            package_override=package_name,
        )

        def restart() -> bool:
            # False: the launcher stops the pass with its reason; going on would relay from any screen.
            send_status("initializing", "Restarting Instagram...")
            return app_service.restart()

        return InstagramRunPhone(
            device_manager=connection.device_manager,
            start=restart,
            installed_version=app_service.get_installed_version,
        )

    def _run_task(self) -> int:
        from taktik.core.kernel.contracts import WorkflowInvocation
        from taktik.core.kernel.registry import WorkflowRegistry
        from taktik.core.social_media.instagram.workflows.tasks import (
            register_instagram_task_handlers,
        )

        registry = WorkflowRegistry()
        register_instagram_task_handlers(
            registry,
            device_id=self.device_id,
            instagram_connect=self._run_phone,
        )

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
            report = handler(invocation, self.params)
        except RunRefused as refused:
            # The launcher's door, before the restart: nothing was opened nor relayed.
            send_run_refusal(refused, "Task")
            return 1
        except Exception as exc:  # noqa: BLE001
            send_run_error(f"Task error: {exc}", exc)
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
