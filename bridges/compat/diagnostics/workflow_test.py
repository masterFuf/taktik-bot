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
from bridges.compat.diagnostics.runtime.workflow_observability import (
    clear_active_watchdog,
    get_last_stats,
    set_active_tracer,
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
    tracer, automation, device = _init_automation(app_name, conn, ipc)

    _apply_version_overrides(app_name, version, ipc)
    _detect_instagram_language(app_name, device, ipc)

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

    _stop_watchdog(dispatch_result.watchdog, ipc)

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


def _init_automation(app_name: str, conn, ipc):
    def _on_xpath(call):
        ipc.send(
            "selector_event",
            xpath=call.xpath,
            found=call.found,
            elapsed_ms=call.elapsed_ms,
            step=call.step,
            error=call.error,
            screen=call.screen,
        )

    from taktik.core.compat.selectors.tracer import SelectorTracer

    tracer = SelectorTracer(on_xpath_call=_on_xpath)

    try:
        from taktik.core.database import configure_db_service

        configure_db_service()

        automation = None
        if app_name == "instagram":
            from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation

            automation = InstagramAutomation(conn.device_manager)
            device = automation.device
        else:
            device = conn.device_manager

        tracer.attach(device)
        set_active_tracer(tracer)

        ipc.send("step", step="init_automation", status="done", message="Automation ready, tracer attached")
        return tracer, automation, device
    except Exception as exc:
        ipc.send("error", error=f"Automation init failed: {exc}", error_code="AUTOMATION_INIT_ERROR")
        logger.exception("Automation init failed")
        sys.exit(1)


def _apply_version_overrides(app_name: str, version: str, ipc) -> None:
    ipc.send(
        "step",
        step="version_overrides",
        status="running",
        message=f"Applying selector overrides for {app_name} v{version}...",
    )
    try:
        from taktik.core.compat.selectors.setup import apply_version_overrides

        patched_count = apply_version_overrides(app_name, version)
        ipc.send("step", step="version_overrides", status="done", message=f"Patched {patched_count} selector(s) for v{version}")
        if patched_count > 0:
            ipc.send(
                "action_event",
                action="version_overrides_applied",
                username="",
                success=True,
                data={"version": version, "patched": patched_count},
            )
    except Exception as exc:
        logger.warning(f"Version override failed (non-fatal): {exc}")
        ipc.send("step", step="version_overrides", status="done", message="Version overrides: skipped (error)")


def _detect_instagram_language(app_name: str, device, ipc) -> None:
    if app_name != "instagram":
        return

    ipc.send("step", step="language_detect", status="running", message="Detecting app language...")
    try:
        from taktik.core.social_media.instagram.ui.language import detect_and_optimize

        detected_lang = detect_and_optimize(device)
        ipc.send("step", step="language_detect", status="done", message=f"Language: {detected_lang.upper()}")
        ipc.send("action_event", action="language_detected", username="", success=True, data={"language": detected_lang})
    except Exception as exc:
        logger.warning(f"Language detection failed (non-fatal): {exc}")
        ipc.send("step", step="language_detect", status="done", message="Language: unknown (detection failed)")


def _stop_watchdog(watchdog, ipc) -> None:
    if not watchdog:
        return

    try:
        watchdog.stop()
        clear_active_watchdog()
        ipc.send("action_event", action="watchdog_stopped", username="", success=True, data=watchdog.stats)
    except Exception:
        clear_active_watchdog()


if __name__ == "__main__":
    main()
