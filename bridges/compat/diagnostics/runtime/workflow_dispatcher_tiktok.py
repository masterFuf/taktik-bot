"""TikTok workflow dispatch for the compat workflow diagnostic bridge."""

from bridges.compat.diagnostics.runtime.workflow_catalog import (
    TIKTOK_AUTOMATION_WF,
    TIKTOK_DM_WF,
    TIKTOK_SCRAPING_WF,
)
from bridges.compat.diagnostics.runtime.workflow_dispatch_result import WorkflowDispatchResult
from bridges.compat.diagnostics.runtime.workflow_runners import (
    run_tiktok_automation,
    run_tiktok_dm,
    run_tiktok_publish,
    run_tiktok_scraping,
    run_tiktok_unfollow,
)


def dispatch_tiktok_workflow(
    *,
    workflow_type: str,
    target: str,
    limits: dict,
    probabilities: dict,
    delays: dict | None,
    conn,
    device,
    tracer,
    ipc,
) -> WorkflowDispatchResult:
    """Dispatch a TikTok workflow family while preserving compat IPC events."""
    result = WorkflowDispatchResult()

    if workflow_type in TIKTOK_AUTOMATION_WF:
        tracer.begin_step(f"tiktok:{workflow_type}")
        result.success = run_tiktok_automation(conn, device, ipc, workflow_type, target, limits, probabilities, delays)
        tracer.end_step(success=result.success)
        return result

    if workflow_type in TIKTOK_DM_WF:
        tracer.begin_step(f"tiktok_dm:{workflow_type}")
        result.success = run_tiktok_dm(conn, device, ipc, workflow_type, limits)
        tracer.end_step(success=result.success)
        return result

    if workflow_type == "unfollow":
        tracer.begin_step("tiktok:unfollow")
        result.success = run_tiktok_unfollow(conn, device, ipc, limits)
        tracer.end_step(success=result.success)
        return result

    if workflow_type == "upload_post":
        tracer.begin_step("tiktok:upload_post")
        result.success = run_tiktok_publish(conn, device, ipc)
        tracer.end_step(success=result.success)
        return result

    if workflow_type in TIKTOK_SCRAPING_WF:
        tracer.begin_step(f"tiktok_scraping:{workflow_type}")
        result.success = run_tiktok_scraping(conn, device, ipc, workflow_type, target, limits)
        tracer.end_step(success=result.success)
        return result

    result.error = f"Unsupported workflow: tiktok/{workflow_type}"
    return result


__all__ = ["dispatch_tiktok_workflow"]
