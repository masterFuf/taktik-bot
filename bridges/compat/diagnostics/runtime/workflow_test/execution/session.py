"""Device/app session setup for the compat workflow diagnostic bridge."""

from dataclasses import dataclass
import sys

from bridges.common.device.app_manager import AppService
from bridges.common.device.connection import ConnectionService
from bridges.compat.diagnostics.runtime.workflow_test.execution.lifecycle import (
    apply_version_overrides,
    detect_instagram_language,
    init_automation,
)


@dataclass
class WorkflowTestSession:
    connection: ConnectionService
    tracer: object
    automation: object | None
    device: object


def prepare_workflow_test_session(*, request, ipc) -> WorkflowTestSession:
    """Connect device, launch app and initialize selector tracing."""
    device_id = request.device_id
    app_name = request.app_name
    version = request.version

    ipc.send("step", step="connect", status="running", message=f"Connecting to {device_id}...")
    conn = ConnectionService(device_id)
    if not conn.connect():
        ipc.send("error", error=f"Failed to connect to {device_id}", error_code="CONNECTION_ERROR")
        sys.exit(1)
    ipc.send("step", step="connect", status="done", message="Connected")

    platform_label = app_name.capitalize()
    ipc.send("step", step="launch", status="running", message=f"Launching {platform_label}...")
    app_service = AppService(conn, platform=app_name)
    if not app_service.is_installed():
        ipc.send("error", error=f"{platform_label} is not installed", error_code="APP_NOT_INSTALLED")
        sys.exit(1)
    if not app_service.launch():
        ipc.send("error", error=f"Failed to launch {platform_label}", error_code="APP_LAUNCH_FAILED")
        sys.exit(1)
    ipc.send("step", step="launch", status="done", message=f"{platform_label} launched")

    ipc.send("step", step="init_automation", status="running", message="Initializing automation engine...")
    tracer, automation, device = init_automation(app_name, conn, ipc)

    apply_version_overrides(app_name, version, ipc)
    detect_instagram_language(app_name, device, ipc)

    return WorkflowTestSession(
        connection=conn,
        tracer=tracer,
        automation=automation,
        device=device,
    )


__all__ = ["WorkflowTestSession", "prepare_workflow_test_session"]
