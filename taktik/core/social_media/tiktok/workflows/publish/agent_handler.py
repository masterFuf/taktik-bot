"""The one launcher of a TikTok publication, and its Agent handler.

`run_tiktok_publish` is what the desktop bridge (`tiktok_publish_bridge`) calls and what the handler
registered as `tiktok.standalone.upload_post` (the CLI) calls: read the request (`payload.py`),
patch the selectors of a cloned TikTok, then upload the video or write the text post. The host
brings a connected device. What differs between hosts is injected:
- `notifier`: where the statuses, logs and the final `upload_result` go (the bridge's stdout IPC;
  the log otherwise).
- `step_hook(phase)`: called before, during and after the publication (the bridge saves a
  screenshot and a UI dump per phase).
"""

from __future__ import annotations

import traceback
from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    merge_invocation_payload,
    notify,
)
from taktik.core.social_media.tiktok.workflows.publish.payload import (
    PublishRequest,
    publish_request_from_payload,
)


TIKTOK_UPLOAD_POST_WORKFLOW_ID = "tiktok.standalone.upload_post"
TikTokUploadWorkflowFactory = Callable[..., Any]
StepHook = Callable[[str], None]


def _default_workflow_factory() -> TikTokUploadWorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.tiktok.workflows.publish import upload_workflow

    return upload_workflow.TikTokUploadWorkflow


def _emit(notifier: Any, method: str, *args: Any) -> None:
    target = getattr(notifier, method, None)
    if callable(target):
        target(*args)


def _step(step_hook: Optional[StepHook], phase: str) -> None:
    if step_hook is not None:
        step_hook(phase)


def _patch_clone_selectors(package_name: Optional[str], notifier: Any) -> None:
    """A cloned TikTok names its resource-ids after its own package: patch the catalogue first."""
    from taktik.core.clone.packages import get_original_package

    if not package_name or package_name == get_original_package("tiktok"):
        return
    try:
        from taktik.core.clone import patch_selectors_for_package, set_active_package

        set_active_package(package_name)
        patched = patch_selectors_for_package("tiktok", package_name)
        _emit(notifier, "log", "info", f"🧬 Package override: patched {patched} selector(s) for {package_name}")
    except Exception as e:
        _emit(notifier, "log", "warning", f"⚠️ Clone selector patching failed (non-fatal): {e}")


def _fail(notifier: Any, message: str) -> dict[str, Any]:
    logger.error(message)
    _emit(notifier, "error", message)
    _emit(notifier, "log", "error", traceback.format_exc())
    return {"success": False, "message": message, "error_type": "exception"}


def _publish_text(request: PublishRequest, device, device_id: str, notifier: Any,
                  step_hook: Optional[StepHook]) -> dict[str, Any]:
    """The TEXT format: no file, no gallery, no upload -- just the composer."""
    _emit(notifier, "status", "running", "Publishing a TikTok text post...")
    try:
        from taktik.core.social_media.tiktok.services.publish import text_post

        _step(step_hook, "00_before")
        result = text_post.publish_text_post(device, device_id, request.text, to_story=request.to_story)
        _step(step_hook, "99_after")
    except Exception as exc:
        return _fail(notifier, f"Text post failed: {exc}")

    success = bool(result.get("success"))
    message = result.get("error") or f"text post published to {result.get('destination')}"
    _emit(notifier, "status", "success" if success else "error", message)
    # The step it stopped at, so a failure says WHERE rather than only that it failed.
    error_type = None if success else result.get("step")
    notify(notifier, "upload_result", success=success, workflow="text_post", message=message, error_type=error_type)
    return {**result, "success": success, "message": message, "error_type": error_type}


def _upload_video(request: PublishRequest, device, device_id: str, notifier: Any,
                  step_hook: Optional[StepHook], workflow_factory) -> dict[str, Any]:
    _emit(notifier, "status", "running", "Starting TikTok upload workflow...")
    try:
        workflow = (workflow_factory or _default_workflow_factory())(
            device, device_id, notifier=notifier, step_hook=step_hook
        )
        _step(step_hook, "00_before")
        result = workflow.execute(
            local_path=request.local_path,
            caption=request.caption,
            hashtags=request.hashtags,
            package_name=request.package_name,
        )
        _step(step_hook, "99_after")
    except Exception as e:
        return _fail(notifier, f"Upload workflow error: {e}")

    success = result.get("success", False)
    _emit(notifier, "status", "success" if success else "error", result.get("message", ""))
    notify(
        notifier,
        "upload_result",
        success=success,
        workflow="upload_post",
        message=result.get("message", ""),
        error_type=result.get("error_type"),
    )
    return result


def run_tiktok_publish(
    payload: Mapping[str, Any],
    *,
    device,
    device_id: str,
    notifier=None,
    step_hook: Optional[StepHook] = None,
    workflow_factory: Optional[TikTokUploadWorkflowFactory] = None,
) -> dict[str, Any]:
    """Publish what a payload asks on `device`. Raises `PublishRequestError` before touching the
    phone when there is nothing to publish."""
    from taktik.core.social_media.tiktok.workflows.runtime.notifier import LoggingWorkflowNotifier

    notifier = notifier if notifier is not None else LoggingWorkflowNotifier()
    request = publish_request_from_payload(payload)
    _patch_clone_selectors(request.package_name, notifier)
    if request.post_type == "text":
        return _publish_text(request, device, device_id, notifier, step_hook)
    return _upload_video(request, device, device_id, notifier, step_hook, workflow_factory)


def build_tiktok_upload_post_handler(
    *,
    device,
    device_id: str,
    notifier=None,
    workflow_factory: Optional[TikTokUploadWorkflowFactory] = None,
) -> WorkflowHandler:
    """Build the publish handler: the same launcher as the desktop bridge, on the host's device."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        return run_tiktok_publish(
            merge_invocation_payload(invocation, payload),
            device=device,
            device_id=device_id,
            notifier=notifier,
            workflow_factory=workflow_factory,
        )

    return handler


def register_tiktok_publish_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    device_id: str,
    notifier=None,
    workflow_factory: Optional[TikTokUploadWorkflowFactory] = None,
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


__all__ = [
    "TIKTOK_UPLOAD_POST_WORKFLOW_ID",
    "build_tiktok_upload_post_handler",
    "register_tiktok_publish_handlers",
    "run_tiktok_publish",
]
