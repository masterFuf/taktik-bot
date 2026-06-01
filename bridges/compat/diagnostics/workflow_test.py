#!/usr/bin/env python3
"""
Workflow Test Bridge â€” Runs a real Instagram workflow with selector instrumentation.

Launches a full workflow (target_followers, hashtag, feed, etc.) on the connected device,
with the SelectorTracer attached to record every XPath call. At the end, generates a
compatibility report showing which selectors worked and which failed.

Config JSON (passed as argv[1] temp file):
  {
    "device_id": "CE7S00081E2148",
    "app": "instagram",
    "version": "417.0.0.54.77",
    "workflow": "target_followers",
    "target": "natgeo",
    "limits": {
      "maxProfiles": 3,
      "maxLikesPerProfile": 1
    },
    "probabilities": {
      "like": 80,
      "follow": 0,
      "comment": 0,
      "watchStories": 0,
      "likeStories": 0
    }
  }

Output: IPC messages with step-by-step progress and a final compatibility report.
"""

import sys
import os
import time

# Bootstrap: ensure bot root is in sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.runtime.ipc import IPC
from bridges.common.device.connection import ConnectionService
from bridges.common.device.app_manager import AppService
from bridges.compat.diagnostics.runtime.workflow_catalog import (
    INSTAGRAM_AUTOMATION_WF,
    INSTAGRAM_DM_WF,
    INSTAGRAM_PUBLISH_WF,
    INSTAGRAM_SCRAPING_WF,
    TIKTOK_AUTOMATION_WF,
    TIKTOK_DM_WF,
    TIKTOK_SCRAPING_WF,
)
from bridges.compat.diagnostics.runtime.instagram_automation import (
    build_workflow_config,
    instrument_workflow_runner,
)
from bridges.compat.diagnostics.runtime.workflow_observability import (
    clear_active_watchdog,
    get_last_stats,
    set_active_tracer,
    set_active_watchdog,
    setup_action_hooks,
    setup_log_sink,
)
from bridges.compat.diagnostics.runtime.workflow_request import load_workflow_test_request
from bridges.compat.diagnostics.runtime.workflow_report import build_workflow_report
from bridges.compat.diagnostics.runtime.workflow_runners import (
    run_instagram_dm,
    run_instagram_publish,
    run_instagram_scraping,
    run_instagram_smart_comment,
    run_tiktok_automation,
    run_tiktok_dm,
    run_tiktok_publish,
    run_tiktok_scraping,
    run_tiktok_unfollow,
)
from loguru import logger


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Workflow runners per category (non-automation)
# Each returns True/False for success.
# They reuse the real workflow code from the bot with tracer attached.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    # Start streaming logs + action events via IPC
    setup_log_sink(ipc)
    setup_action_hooks(ipc)

    logger.info(f"[WorkflowTest] device={device_id} app={app_name} v={version} workflow={workflow_type} target={target}")
    ipc.send("status", status="initializing", message="Initializing workflow test...")

    # ------------------------------------------------------------------
    # Step 1: Connect to device
    # ------------------------------------------------------------------
    ipc.send("step", step="connect", status="running", message=f"Connecting to {device_id}...")
    conn = ConnectionService(device_id)
    if not conn.connect():
        ipc.send("error", error=f"Failed to connect to {device_id}", error_code="CONNECTION_ERROR")
        sys.exit(1)
    ipc.send("step", step="connect", status="done", message="Connected")

    # ------------------------------------------------------------------
    # Step 2: Launch app (Instagram or TikTok)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Step 3: Initialize automation + attach tracer
    # ------------------------------------------------------------------
    ipc.send("step", step="init_automation", status="running", message="Initializing automation engine...")

    # Create the SelectorTracer with real-time IPC callback
    def _on_xpath(call):
        ipc.send("selector_event",
                 xpath=call.xpath,
                 found=call.found,
                 elapsed_ms=call.elapsed_ms,
                 step=call.step,
                 error=call.error,
                 screen=call.screen)

    from taktik.core.compat.selectors.tracer import SelectorTracer

    tracer = SelectorTracer(on_xpath_call=_on_xpath)
    automation = None
    device = None

    try:
        from taktik.core.database import configure_db_service
        configure_db_service()

        if app_name == "instagram":
            from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation
            automation = InstagramAutomation(conn.device_manager)
            device = automation.device
        elif app_name == "tiktok":
            # TikTok uses device_manager directly for most workflows
            device = conn.device_manager
        else:
            device = conn.device_manager

        tracer.attach(device)
        set_active_tracer(tracer)

        ipc.send("step", step="init_automation", status="done", message="Automation ready, tracer attached")
    except Exception as e:
        ipc.send("error", error=f"Automation init failed: {e}", error_code="AUTOMATION_INIT_ERROR")
        logger.exception("Automation init failed")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 3b: Apply version-specific selector overrides
    # ------------------------------------------------------------------
    ipc.send("step", step="version_overrides", status="running",
             message=f"Applying selector overrides for {app_name} v{version}...")
    try:
        from taktik.core.compat.selectors.setup import apply_version_overrides
        patched_count = apply_version_overrides(app_name, version)
        ipc.send("step", step="version_overrides", status="done",
                 message=f"Patched {patched_count} selector(s) for v{version}")
        if patched_count > 0:
            ipc.send("action_event", action="version_overrides_applied", username="",
                     success=True, data={"version": version, "patched": patched_count})
    except Exception as e:
        logger.warning(f"Version override failed (non-fatal): {e}")
        ipc.send("step", step="version_overrides", status="done",
                 message="Version overrides: skipped (error)")

    # ------------------------------------------------------------------
    # Step 3c: Detect app language and optimize selectors (Instagram only)
    # ------------------------------------------------------------------
    if app_name == "instagram":
        ipc.send("step", step="language_detect", status="running", message="Detecting app language...")
        try:
            from taktik.core.social_media.instagram.ui.language import detect_and_optimize
            detected_lang = detect_and_optimize(device)
            ipc.send("step", step="language_detect", status="done",
                     message=f"Language: {detected_lang.upper()}")
            ipc.send("action_event", action="language_detected", username="",
                     success=True, data={"language": detected_lang})
        except Exception as e:
            logger.warning(f"Language detection failed (non-fatal): {e}")
            ipc.send("step", step="language_detect", status="done",
                     message="Language: unknown (detection failed)")

    # ------------------------------------------------------------------
    # Step 4: Run the workflow (dispatch by platform + category)
    # ------------------------------------------------------------------
    ipc.send("step", step="run_workflow", status="running",
             message=f"Running {workflow_type} workflow (target={target})...")

    watchdog = None
    workflow_success = False
    workflow_error = None
    start_time = time.time()

    try:
        # â”€â”€ Instagram Automation workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if app_name == "instagram" and workflow_type in INSTAGRAM_AUTOMATION_WF:
            workflow_config = build_workflow_config(workflow_type, target, limits, probs, session_duration, delays)
            automation.config = workflow_config

            # Start the watchdog to detect stuck states and auto-recover
            try:
                from taktik.core.social_media.instagram.ui.watchdog import WorkflowWatchdog
                watchdog = WorkflowWatchdog(
                    device, ipc=ipc,
                    stuck_timeout=90, check_interval=15, max_recoveries=5,
                )
                set_active_watchdog(watchdog)
                watchdog.start()
                ipc.send("action_event", action="watchdog_started", username="",
                         success=True, data={"timeout": 90})
            except Exception as e:
                logger.warning(f"[WorkflowTest] Could not start watchdog (non-fatal): {e}")

            instrument_workflow_runner(automation, tracer, ipc)
            automation.run_workflow()
            workflow_success = True

        # â”€â”€ Instagram Scraping workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "instagram" and workflow_type in INSTAGRAM_SCRAPING_WF:
            tracer.begin_step(f"scraping:{workflow_type}")
            workflow_success = run_instagram_scraping(conn, device, ipc, workflow_type, target, limits, delays)
            tracer.end_step(success=workflow_success)

        # â”€â”€ Instagram DM workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "instagram" and workflow_type in INSTAGRAM_DM_WF:
            tracer.begin_step(f"dm:{workflow_type}")
            workflow_success = run_instagram_dm(conn, device, ipc, workflow_type, limits, delays)
            tracer.end_step(success=workflow_success)

        # â”€â”€ Instagram Smart Comment â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "instagram" and workflow_type == "smart_comment":
            tracer.begin_step("smart_comment")
            workflow_success = run_instagram_smart_comment(conn, device, ipc, target, limits, delays)
            tracer.end_step(success=workflow_success)

        # â”€â”€ Instagram Publish workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "instagram" and workflow_type in INSTAGRAM_PUBLISH_WF:
            tracer.begin_step(f"publish:{workflow_type}")
            workflow_success = run_instagram_publish(conn, device, ipc, workflow_type)
            tracer.end_step(success=workflow_success)


        # â”€â”€ TikTok Automation workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "tiktok" and workflow_type in TIKTOK_AUTOMATION_WF:
            tracer.begin_step(f"tiktok:{workflow_type}")
            workflow_success = run_tiktok_automation(conn, device, ipc, workflow_type, target, limits, probs, delays)
            tracer.end_step(success=workflow_success)

        # â”€â”€ TikTok DM workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "tiktok" and workflow_type in TIKTOK_DM_WF:
            tracer.begin_step(f"tiktok_dm:{workflow_type}")
            workflow_success = run_tiktok_dm(conn, device, ipc, workflow_type, limits)
            tracer.end_step(success=workflow_success)

        # â”€â”€ TikTok Unfollow â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "tiktok" and workflow_type == "unfollow":
            tracer.begin_step("tiktok:unfollow")
            workflow_success = run_tiktok_unfollow(conn, device, ipc, limits)
            tracer.end_step(success=workflow_success)

        # â”€â”€ TikTok Publish â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "tiktok" and workflow_type == "upload_post":
            tracer.begin_step("tiktok:upload_post")
            workflow_success = run_tiktok_publish(conn, device, ipc)
            tracer.end_step(success=workflow_success)

        # â”€â”€ TikTok Scraping â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif app_name == "tiktok" and workflow_type in TIKTOK_SCRAPING_WF:
            tracer.begin_step(f"tiktok_scraping:{workflow_type}")
            workflow_success = run_tiktok_scraping(conn, device, ipc, workflow_type, target, limits)
            tracer.end_step(success=workflow_success)


        else:
            workflow_error = f"Unsupported workflow: {app_name}/{workflow_type}"
            ipc.send("step", step="run_workflow", status="error", message=workflow_error)

    except Exception as e:
        workflow_error = str(e)
        logger.exception(f"Workflow error: {e}")
        ipc.send("step", step="run_workflow", status="error", message=f"Workflow error: {e}")

    # Stop watchdog
    if watchdog:
        try:
            watchdog.stop()
            clear_active_watchdog()
            ipc.send("action_event", action="watchdog_stopped", username="",
                     success=True, data=watchdog.stats)
        except Exception:
            clear_active_watchdog()

    elapsed_s = round(time.time() - start_time, 1)

    # ------------------------------------------------------------------
    # Step 5: Generate report
    # ------------------------------------------------------------------
    ipc.send("step", step="report", status="running", message="Generating compatibility report...")

    tracer.detach()
    report, score, status, status_message = build_workflow_report(
        tracer,
        workflow_type=workflow_type,
        target=target,
        workflow_success=workflow_success,
        workflow_error=workflow_error,
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

    # Send final report
    ipc.send("test_report", **report)

    # Summary status
    ipc.send("status", status=status, message=status_message)

    conn.disconnect()
    logger.info(f"[WorkflowTest] Done: score={score}%, workflow_success={workflow_success}")


if __name__ == "__main__":
    main()
