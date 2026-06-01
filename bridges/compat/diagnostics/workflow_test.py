#!/usr/bin/env python3
"""
Workflow Test Bridge.

Runs a real Instagram or TikTok workflow with selector instrumentation and emits
JSON IPC messages consumed by Electron. Keep stdout JSON-only.
"""

import os
import sys
import time


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from loguru import logger

from bridges.common.device.app_manager import AppService
from bridges.common.device.connection import ConnectionService
from bridges.common.runtime.ipc import IPC
from bridges.compat.diagnostics.runtime.workflow_dispatcher import dispatch_workflow
from bridges.compat.diagnostics.runtime.workflow_lifecycle import (
    apply_version_overrides,
    detect_instagram_language,
    init_automation,
    stop_watchdog,
)
from bridges.compat.diagnostics.runtime.workflow_observability import (
    get_last_stats,
    setup_action_hooks,
    setup_log_sink,
)
from bridges.compat.diagnostics.runtime.workflow_report import build_workflow_report
from bridges.compat.diagnostics.runtime.workflow_request import load_workflow_test_request


def main():
    ipc = IPC()

    request = load_workflow_test_request(ipc, sys.argv)
    device_id = request.device_id
    app_name = request.app_name
    version = request.version
    workflow_type = request.workflow_type
    target = request.target
    limits = request.limits
    probs = request.probabilities
    session_duration = request.session_duration
    delays = request.delays

    setup_log_sink(ipc)
    setup_action_hooks(ipc)

    logger.info(f"[WorkflowTest] device={device_id} app={app_name} v={version} workflow={workflow_type} target={target}")
    ipc.send("status", status="initializing", message="Initializing workflow test...")

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

    ipc.send(
        "step",
        step="run_workflow",
        status="running",
        message=f"Running {workflow_type} workflow (target={target})...",
    )
    start_time = time.time()
    dispatch_result = dispatch_workflow(
        app_name=app_name,
        workflow_type=workflow_type,
        target=target,
        limits=limits,
        probabilities=probs,
        session_duration=session_duration,
        delays=delays,
        conn=conn,
        device=device,
        automation=automation,
        tracer=tracer,
        ipc=ipc,
    )

    stop_watchdog(dispatch_result.watchdog, ipc)

    elapsed_s = round(time.time() - start_time, 1)
    ipc.send("step", step="report", status="running", message="Generating compatibility report...")

    tracer.detach()
    report, score, status, status_message = build_workflow_report(
        tracer,
        workflow_type=workflow_type,
        target=target,
        workflow_success=dispatch_result.success,
        workflow_error=dispatch_result.error,
        elapsed_s=elapsed_s,
        limits=limits,
        probs=probs,
        session_duration=session_duration,
        delays=delays,
        app_name=app_name,
        version=version,
        device_id=device_id,
        last_stats=get_last_stats(),
    )

    ipc.send("test_report", **report)
    ipc.send("status", status=status, message=status_message)

    conn.disconnect()
    logger.info(f"[WorkflowTest] Done: score={score}%, workflow_success={dispatch_result.success}")


if __name__ == "__main__":
    main()
