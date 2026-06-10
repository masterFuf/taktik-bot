"""Instagram workflow dispatch for the compat workflow diagnostic bridge."""

from loguru import logger

from bridges.compat.diagnostics.runtime.workflow_test.platforms.instagram.automation import (
    build_workflow_config,
    instrument_workflow_runner,
)
from bridges.compat.diagnostics.runtime.workflow_test.config.catalog import (
    INSTAGRAM_AUTOMATION_WF,
    INSTAGRAM_DM_WF,
    INSTAGRAM_PUBLISH_WF,
    INSTAGRAM_SCRAPING_WF,
)
from bridges.compat.diagnostics.runtime.workflow_test.contracts.dispatch import WorkflowDispatchResult
from bridges.compat.diagnostics.runtime.workflow_test.observability import set_active_watchdog
from bridges.compat.diagnostics.runtime.workflow_test.execution.runners import (
    run_instagram_dm,
    run_instagram_publish,
    run_instagram_scraping,
    run_instagram_smart_comment,
)


def dispatch_instagram_workflow(
    *,
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
    filters: dict | None = None,
    max_consecutive_known: int | None = None,
    behavior_policy: dict | None = None,
) -> WorkflowDispatchResult:
    """Dispatch an Instagram workflow family while preserving compat IPC events."""
    result = WorkflowDispatchResult()

    if workflow_type in INSTAGRAM_AUTOMATION_WF:
        result.watchdog = _run_instagram_automation(
            workflow_type=workflow_type,
            target=target,
            limits=limits,
            probabilities=probabilities,
            session_duration=session_duration,
            delays=delays,
            filters=filters,
            max_consecutive_known=max_consecutive_known,
            behavior_policy=behavior_policy,
            automation=automation,
            device=device,
            tracer=tracer,
            ipc=ipc,
        )
        result.success = True
        return result

    if workflow_type in INSTAGRAM_SCRAPING_WF:
        tracer.begin_step(f"scraping:{workflow_type}")
        result.success = run_instagram_scraping(conn, device, ipc, workflow_type, target, limits, delays)
        tracer.end_step(success=result.success)
        return result

    if workflow_type in INSTAGRAM_DM_WF:
        tracer.begin_step(f"dm:{workflow_type}")
        result.success = run_instagram_dm(conn, device, ipc, workflow_type, limits, delays)
        tracer.end_step(success=result.success)
        return result

    if workflow_type == "smart_comment":
        tracer.begin_step("smart_comment")
        result.success = run_instagram_smart_comment(conn, device, ipc, target, limits, delays)
        tracer.end_step(success=result.success)
        return result

    if workflow_type in INSTAGRAM_PUBLISH_WF:
        tracer.begin_step(f"publish:{workflow_type}")
        result.success = run_instagram_publish(conn, device, ipc, workflow_type)
        tracer.end_step(success=result.success)
        return result

    result.error = f"Unsupported workflow: instagram/{workflow_type}"
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
    filters: dict | None = None,
    max_consecutive_known: int | None = None,
    behavior_policy: dict | None = None,
):
    workflow_config = build_workflow_config(
        workflow_type, target, limits, probabilities, session_duration, delays,
        filters=filters, max_consecutive_known=max_consecutive_known,
        behavior_policy=behavior_policy,
    )
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


__all__ = ["dispatch_instagram_workflow"]
