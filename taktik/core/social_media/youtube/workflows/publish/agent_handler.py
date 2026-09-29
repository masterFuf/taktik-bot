"""The one launcher of a YouTube upload, and its Agent handler.

`run_youtube_upload` is what the upload bridge and the handler registered as
`youtube.publish.upload_post` (the CLI) call: it reads the payload (`payload.py`), refuses a
missing file, then uploads on the device the host brings. What differs between hosts is
injected: `log` and `status`, where the workflow's lines go.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.kernel.contracts import WorkflowInvocation
from taktik.core.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.youtube.workflows.publish.payload import (
    SHORT_TITLE_MAX_LENGTH,
    check_upload_file,
    youtube_upload_request_from_payload,
)
from taktik.core.social_media.youtube.workflows.publish.upload_workflow import (
    YouTubeUploadWorkflow,
    set_callbacks,
)


YOUTUBE_UPLOAD_POST_WORKFLOW_ID = "youtube.publish.upload_post"
YouTubeUploadWorkflowFactory = Callable[..., Any]


def run_youtube_upload(
    payload: Mapping[str, Any],
    *,
    device,
    device_id: str,
    log=None,
    status=None,
    workflow_factory: YouTubeUploadWorkflowFactory = YouTubeUploadWorkflow,
) -> dict[str, Any]:
    """Read the payload, refuse a missing file, wire the host's callbacks, then upload."""
    request = youtube_upload_request_from_payload(payload)
    check_upload_file(request)
    set_callbacks(log=log, status=status)
    if request.title_trimmed and log is not None:
        log("warning", f"YouTube Shorts title trimmed to {SHORT_TITLE_MAX_LENGTH} characters")
    workflow = workflow_factory(device, device_id)
    return workflow.execute(**request.workflow_params())


def build_youtube_upload_post_handler(
    *,
    device,
    device_id: str,
    notifier=None,
    workflow_factory: YouTubeUploadWorkflowFactory = YouTubeUploadWorkflow,
) -> WorkflowHandler:
    """Build a WorkflowRegistry handler without owning device connection setup."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = dict(payload)
        merged.update(invocation.params)
        return run_youtube_upload(
            merged,
            device=device,
            device_id=device_id,
            log=getattr(notifier, "log", None),
            status=getattr(notifier, "status", None),
            workflow_factory=workflow_factory,
        )

    return handler


def register_youtube_publish_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    device_id: str,
    notifier=None,
    workflow_factory: YouTubeUploadWorkflowFactory = YouTubeUploadWorkflow,
) -> WorkflowRegistry:
    """Register YouTube publish handlers into an injected agent WorkflowRegistry."""
    registry.register(
        YOUTUBE_UPLOAD_POST_WORKFLOW_ID,
        build_youtube_upload_post_handler(
            device=device,
            device_id=device_id,
            notifier=notifier,
            workflow_factory=workflow_factory,
        ),
    )
    return registry
