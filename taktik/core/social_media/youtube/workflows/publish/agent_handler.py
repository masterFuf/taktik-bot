"""Agent runtime handler for the YouTube publish workflow."""

from __future__ import annotations

import os
from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.youtube.workflows.publish.upload_workflow import (
    YouTubeUploadWorkflow,
    set_callbacks,
)


YOUTUBE_UPLOAD_POST_WORKFLOW_ID = "youtube.publish.upload_post"
SHORT_TITLE_MAX_LENGTH = 100
YouTubeUploadWorkflowFactory = Callable[..., Any]


def build_youtube_upload_post_handler(
    *,
    device,
    device_id: str,
    notifier=None,
    workflow_factory: YouTubeUploadWorkflowFactory = YouTubeUploadWorkflow,
) -> WorkflowHandler:
    """Build a WorkflowRegistry handler without owning device connection setup."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        params = _publish_params(invocation, payload)
        if notifier is not None:
            set_callbacks(
                log=getattr(notifier, "log", None),
                status=getattr(notifier, "status", None),
            )
        workflow = workflow_factory(device, device_id)
        return workflow.execute(**params)

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


def _publish_params(invocation: WorkflowInvocation, payload: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(payload)
    merged.update(invocation.params)

    local_path = merged.get("local_path") or merged.get("localPath")
    if not isinstance(local_path, str) or not local_path:
        raise ValueError("YouTube upload_post requires a non-empty localPath")
    if not os.path.isfile(local_path):
        raise ValueError(f"File not found: {local_path}")

    upload_type = _string_param(merged, "upload_type", "uploadType", default="short").lower()
    visibility = _string_param(merged, "visibility", default="public").lower()
    title = _trim_short_title(_string_param(merged, "title", default=""), upload_type)

    return {
        "local_path": local_path,
        "title": title,
        "description": _string_param(merged, "description", default=""),
        "upload_type": upload_type,
        "visibility": visibility,
    }


def _string_param(payload: Mapping[str, Any], *names: str, default: str) -> str:
    for name in names:
        value = payload.get(name)
        if value is not None:
            return value if isinstance(value, str) else str(value)
    return default


def _trim_short_title(title: str, upload_type: str) -> str:
    if upload_type != "short" or not title:
        return title
    chars = list(title.strip())
    if len(chars) <= SHORT_TITLE_MAX_LENGTH:
        return title.strip()
    return "".join(chars[:SHORT_TITLE_MAX_LENGTH]).strip()
