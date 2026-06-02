"""Workflow dispatch for the compat workflow diagnostic bridge."""

from loguru import logger

from bridges.compat.diagnostics.runtime.workflow_test.dispatch_result import WorkflowDispatchResult
from bridges.compat.diagnostics.runtime.workflow_test.platforms.instagram.dispatcher import dispatch_instagram_workflow
from bridges.compat.diagnostics.runtime.workflow_test.platforms.tiktok.dispatcher import dispatch_tiktok_workflow


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
        if app_name == "instagram":
            result = dispatch_instagram_workflow(
                workflow_type=workflow_type,
                target=target,
                limits=limits,
                probabilities=probabilities,
                session_duration=session_duration,
                delays=delays,
                conn=conn,
                automation=automation,
                device=device,
                tracer=tracer,
                ipc=ipc,
            )

        elif app_name == "tiktok":
            result = dispatch_tiktok_workflow(
                workflow_type=workflow_type,
                target=target,
                limits=limits,
                probabilities=probabilities,
                delays=delays,
                conn=conn,
                device=device,
                tracer=tracer,
                ipc=ipc,
            )
        else:
            result.error = f"Unsupported workflow: {app_name}/{workflow_type}"

        if result.error:
            ipc.send("step", step="run_workflow", status="error", message=result.error)

    except Exception as exc:
        result.error = str(exc)
        logger.exception(f"Workflow error: {exc}")
        ipc.send("step", step="run_workflow", status="error", message=f"Workflow error: {exc}")

    return result


__all__ = ["WorkflowDispatchResult", "dispatch_workflow"]
