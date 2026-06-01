"""Workflow execution for the YouTube upload bridge."""

from typing import Any, Callable


def run_youtube_upload_workflow(
    *,
    device: Any,
    device_id: str,
    request: Any,
    send_status: Callable[[str, str], None],
    send_message: Callable[..., None],
    send_error: Callable[[str], None],
    send_log: Callable[[str, str], None],
) -> int:
    """Run the YouTube upload workflow and emit the historical upload_result payload."""
    send_status("running", "Starting YouTube upload workflow...")
    try:
        from taktik.core.social_media.youtube.workflows.publish.upload_workflow import (
            YouTubeUploadWorkflow,
            set_callbacks as set_upload_callbacks,
        )

        # Keep core workflow bridge-agnostic by injecting stdout callbacks here.
        set_upload_callbacks(log=send_log, status=send_status)

        workflow = YouTubeUploadWorkflow(device, device_id)
        result = workflow.execute(
            local_path=request.local_path,
            title=request.title,
            description=request.description,
            upload_type=request.upload_type,
            visibility=request.visibility,
        )

        success = bool(result.get("success", False))
        send_status("success" if success else "error", result.get("message", ""))
        send_message(
            "upload_result",
            success=success,
            workflow="upload_post",
            upload_type=request.upload_type,
            message=result.get("message", ""),
            error_type=result.get("error_type"),
        )
        return 0 if success else 1

    except Exception as exc:
        import traceback

        send_error(f"Upload workflow error: {exc}")
        send_log("error", traceback.format_exc())
        return 1
