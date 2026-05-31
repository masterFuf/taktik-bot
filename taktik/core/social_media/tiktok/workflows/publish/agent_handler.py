"""Agent runtime handler for the TikTok publish workflow."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.workflows.publish.upload_workflow import TikTokUploadWorkflow


TIKTOK_UPLOAD_POST_WORKFLOW_ID = "tiktok.standalone.upload_post"
TikTokUploadWorkflowFactory = Callable[..., Any]


def build_tiktok_upload_post_handler(
    *,
    device,
    device_id: str,
    notifier=None,
    workflow_factory: TikTokUploadWorkflowFactory = TikTokUploadWorkflow,
) -> WorkflowHandler:
    """Build a WorkflowRegistry handler without owning device connection setup."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        params = _publish_params(invocation, payload)
        workflow = workflow_factory(device, device_id, notifier=notifier)
        return workflow.execute(**params)

    return handler


def register_tiktok_publish_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    device_id: str,
    notifier=None,
    workflow_factory: TikTokUploadWorkflowFactory = TikTokUploadWorkflow,
) -> WorkflowRegistry:
    """Register TikTok publish handlers into an injected agent WorkflowRegistry."""
    registry.register(
        TIKTOK_UPLOAD_POST_WORKFLOW_ID,
        build_tiktok_upload_post_handler(
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
        raise ValueError("TikTok upload_post requires a non-empty localPath")

    caption = merged.get("caption") or ""
    if not isinstance(caption, str):
        caption = str(caption)

    hashtags = _hashtags(merged.get("hashtags"))
    package_name = merged.get("package_name") or merged.get("packageName")
    if package_name is not None and not isinstance(package_name, str):
        package_name = str(package_name)

    return {
        "local_path": local_path,
        "caption": caption,
        "hashtags": hashtags,
        "package_name": package_name,
    }


def _hashtags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    raise ValueError("TikTok upload_post hashtags must be a list of strings")
