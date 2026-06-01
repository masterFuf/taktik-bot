"""Workflow dispatch for the compat workflow diagnostic bridge."""

from dataclasses import dataclass

from loguru import logger

from bridges.compat.diagnostics.runtime.instagram_automation import (
    build_workflow_config,
    instrument_workflow_runner,
)
from bridges.compat.diagnostics.runtime.workflow_catalog import (
    INSTAGRAM_AUTOMATION_WF,
    INSTAGRAM_DM_WF,
    INSTAGRAM_PUBLISH_WF,
    INSTAGRAM_SCRAPING_WF,
    TIKTOK_AUTOMATION_WF,
    TIKTOK_DM_WF,
    TIKTOK_SCRAPING_WF,
)
from bridges.compat.diagnostics.runtime.workflow_observability import set_active_watchdog
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


@dataclass
class WorkflowDispatchResult:
    success: bool = False
    error: str | None = None
    watchdog: object | None = None


def dispatch_workflow(
    *,
    app_name: str,
    workflow_type: str,
    target: str,
    limits: dict,
    probabilities: dict,
    session_duration: int,
    delays: dict | None,
    conn,
    device,
    automation,
    tracer,
    ipc,
) -> WorkflowDispatchResult:
    """Dispatch a workflow family while preserving compat diagnostic IPC events."""
    result = WorkflowDispatchResult()

    try:
        if app_name == "instagram" and workflow_type in INSTAGRAM_AUTOMATION_WF:
            result.watchdog = _run_instagram_automation(
                workflow_type=workflow_type,
                target=target,
                limits=limits,
                probabilities=probabilities,
                session_duration=session_duration,
                delays=delays,
                automation=automation,
                device=device,
                tracer=tracer,
                ipc=ipc,
            )
            result.success = True

        elif app_name == "instagram" and workflow_type in INSTAGRAM_SCRAPING_WF:
            tracer.begin_step(f"scraping:{workflow_type}")
            result.success = run_instagram_scraping(conn, device, ipc, workflow_type, target, limits, delays)
            tracer.end_step(success=result.success)

        elif app_name == "instagram" and workflow_type in INSTAGRAM_DM_WF:
            tracer.begin_step(f"dm:{workflow_type}")
            result.success = run_instagram_dm(conn, device, ipc, workflow_type, limits, delays)
            tracer.end_step(success=result.success)

        elif app_name == "instagram" and workflow_type == "smart_comment":
            tracer.begin_step("smart_comment")
            result.success = run_instagram_smart_comment(conn, device, ipc, target, limits, delays)
            tracer.end_step(success=result.success)

        elif app_name == "instagram" and workflow_type in INSTAGRAM_PUBLISH_WF:
            tracer.begin_step(f"publish:{workflow_type}")
            result.success = run_instagram_publish(conn, device, ipc, workflow_type)
            tracer.end_step(success=result.success)

        elif app_name == "tiktok" and workflow_type in TIKTOK_AUTOMATION_WF:
            tracer.begin_step(f"tiktok:{workflow_type}")
            result.success = run_tiktok_automation(conn, device, ipc, workflow_type, target, limits, probabilities, delays)
            tracer.end_step(success=result.success)

        elif app_name == "tiktok" and workflow_type in TIKTOK_DM_WF:
            tracer.begin_step(f"tiktok_dm:{workflow_type}")
            result.success = run_tiktok_dm(conn, device, ipc, workflow_type, limits)
            tracer.end_step(success=result.success)

        elif app_name == "tiktok" and workflow_type == "unfollow":
            tracer.begin_step("tiktok:unfollow")
            result.success = run_tiktok_unfollow(conn, device, ipc, limits)
            tracer.end_step(success=result.success)

        elif app_name == "tiktok" and workflow_type == "upload_post":
            tracer.begin_step("tiktok:upload_post")
            result.success = run_tiktok_publish(conn, device, ipc)
            tracer.end_step(success=result.success)

        elif app_name == "tiktok" and workflow_type in TIKTOK_SCRAPING_WF:
            tracer.begin_step(f"tiktok_scraping:{workflow_type}")
            result.success = run_tiktok_scraping(conn, device, ipc, workflow_type, target, limits)
            tracer.end_step(success=result.success)

        else:
            result.error = f"Unsupported workflow: {app_name}/{workflow_type}"
            ipc.send("step", step="run_workflow", status="error", message=result.error)

    except Exception as exc:
        result.error = str(exc)
        logger.exception(f"Workflow error: {exc}")
        ipc.send("step", step="run_workflow", status="error", message=f"Workflow error: {exc}")

    return result


def _run_instagram_automation(
    *,
    workflow_type: str,
    target: str,
    limits: dict,
    probabilities: dict,
    session_duration: int,
    delays: dict | None,
    automation,
    device,
    tracer,
    ipc,
):
    workflow_config = build_workflow_config(workflow_type, target, limits, probabilities, session_duration, delays)
    automation.config = workflow_config

    watchdog = None
    try:
        from taktik.core.social_media.instagram.ui.watchdog import WorkflowWatchdog

        watchdog = WorkflowWatchdog(
            device,
            ipc=ipc,
            stuck_timeout=90,
            check_interval=15,
            max_recoveries=5,
        )
        set_active_watchdog(watchdog)
        watchdog.start()
        ipc.send("action_event", action="watchdog_started", username="", success=True, data={"timeout": 90})
    except Exception as exc:
        logger.warning(f"[WorkflowTest] Could not start watchdog (non-fatal): {exc}")

    instrument_workflow_runner(automation, tracer, ipc)
    automation.run_workflow()
    return watchdog


__all__ = ["WorkflowDispatchResult", "dispatch_workflow"]
