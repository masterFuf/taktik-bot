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

from bridges.common.runtime.entrypoint import CONFIG_ERROR, MISSING_CONFIG, run_bridge_main
from bridges.common.runtime.ipc import IPC
from bridges.compat.diagnostics.runtime.workflow_test.execution.dispatcher import dispatch_workflow
from bridges.compat.diagnostics.runtime.workflow_test.execution.lifecycle import stop_watchdog
from bridges.compat.diagnostics.runtime.workflow_test.observability import (
    get_last_stats,
    setup_action_hooks,
    setup_log_sink,
)
from bridges.compat.diagnostics.runtime.workflow_test.reporting.report import build_workflow_report
from bridges.compat.diagnostics.runtime.workflow_test.config.request import (
    load_workflow_test_request,
    report_workflow_test_entry_error,
)
from bridges.compat.diagnostics.runtime.workflow_test.execution.session import prepare_workflow_test_session


class _WorkflowTestRun:
    def __init__(self, ipc: IPC, config: dict):
        self.ipc = ipc
        self.config = config

    def run(self) -> int:
        run_workflow_test(self.ipc, self.config)
        return 0


def main():
    ipc = IPC()
    run_bridge_main(lambda config: _WorkflowTestRun(ipc, config), usage="workflow_test_bridge <config.json>",
                    report_error=report_workflow_test_entry_error(ipc),
                    messages={MISSING_CONFIG: "No config file provided", CONFIG_ERROR: "Failed to read config: {error}"}, catch_crashes=False)


def run_workflow_test(ipc: IPC, config: dict) -> None:
    request = load_workflow_test_request(ipc, config)
    device_id = request.device_id
    app_name = request.app_name
    version = request.version
    workflow_type = request.workflow_type
    target = request.target
    limits = request.limits
    probs = request.probabilities
    session_duration = request.session_duration
    delays = request.delays
    filters = request.filters
    max_consecutive_known = request.max_consecutive_known
    behavior_policy = request.behavior_policy
    options = request.options

    setup_log_sink(ipc)
    setup_action_hooks(ipc)

    logger.info(f"[WorkflowTest] device={device_id} app={app_name} v={version} workflow={workflow_type} target={target}")
    ipc.send("status", status="initializing", message="Initializing workflow test...")

    session = prepare_workflow_test_session(request=request, ipc=ipc)

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
        filters=filters,
        max_consecutive_known=max_consecutive_known,
        behavior_policy=behavior_policy,
        options=options,
        conn=session.connection,
        device=session.device,
        automation=session.automation,
        tracer=session.tracer,
        ipc=ipc,
    )

    stop_watchdog(dispatch_result.watchdog, ipc)

    elapsed_s = round(time.time() - start_time, 1)
    ipc.send("step", step="report", status="running", message="Generating compatibility report...")

    session.tracer.detach()
    report, score, status, status_message = build_workflow_report(
        session.tracer,
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

    session.connection.disconnect()
    logger.info(f"[WorkflowTest] Done: score={score}%, workflow_success={dispatch_result.success}")


if __name__ == "__main__":
    main()
