"""The one launcher of an Instagram publication, and its Agent handler.

`run_instagram_publish` is what the desktop bridge (`publish_bridge`) calls, what the handler
registered as `instagram.content.publish` (the CLI's `taktik workflows run`) calls, what the
`taktik publish` commands and the Lab's publish bench call: read the request (`payload.py`),
refuse what cannot be published before the phone is touched, then run `InstagramPostWorkflow`,
the only publishing engine. What differs between hosts is injected:
- `connect() -> device`: the phone, connected by the host (the bridge's connection, the device the
  CLI or the Lab already holds), called once the request is accepted;
- `log(level, message)`, `status(status, message)`: where the workflow's lines go (the bridge's
  stdout, the terminal, the Lab's report; the log otherwise).
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.publish.payload import (
    publish_request_from_payload,
    published_kind,
)

INSTAGRAM_CONTENT_PUBLISH_WORKFLOW_ID = "instagram.content.publish"

#: `connect() -> device`: the connected phone the publication runs on.
Connect = Callable[[], Any]
LogCallback = Callable[[str, str], None]
StatusCallback = Callable[[str, str], None]
InstagramPostWorkflowFactory = Callable[..., Any]


def _default_workflow_factory() -> InstagramPostWorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.instagram.workflows.publish import post_workflow

    return post_workflow.InstagramPostWorkflow


def _log_to_logger(level: str, message: str) -> None:
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def run_instagram_publish(
    payload: Mapping[str, Any],
    *,
    device_id: str,
    connect: Connect,
    log: Optional[LogCallback] = None,
    status: Optional[StatusCallback] = None,
    workflow_factory: Optional[InstagramPostWorkflowFactory] = None,
) -> dict[str, Any]:
    """Publish what a payload asks. Raises `PublishRequestError` before touching the phone when
    there is nothing to publish; returns the workflow's result otherwise (`success`, `message`,
    `error_type`, `confirmed`)."""
    request = publish_request_from_payload(payload)
    device = connect()
    workflow = (workflow_factory or _default_workflow_factory())(
        device,
        device_id,
        log=log or _log_to_logger,
        status=status,
        package_name=request.package_name,
        post_type=published_kind(request),
        story_via_feed=request.story_via_feed,
        account_username=request.bot_username,
    )
    return workflow.execute(
        caption=request.caption,
        hashtags=request.hashtags,
        media_paths=request.media_paths,
        stop_before_share=request.stop_before_share,
    )


def build_instagram_publish_handler(*, device, device_id: str) -> WorkflowHandler:
    """Build the publish handler: the same launcher as the desktop bridge, on the host's device."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = dict(payload)
        merged.update(invocation.params)
        return run_instagram_publish(merged, device_id=device_id, connect=lambda: device)

    return handler


def register_instagram_publish_handlers(registry: WorkflowRegistry, *, device, device_id: str) -> WorkflowRegistry:
    """Register the Instagram publish handler into an injected Agent registry."""
    registry.register(
        INSTAGRAM_CONTENT_PUBLISH_WORKFLOW_ID,
        build_instagram_publish_handler(device=device, device_id=device_id),
    )
    return registry


__all__ = [
    "INSTAGRAM_CONTENT_PUBLISH_WORKFLOW_ID",
    "build_instagram_publish_handler",
    "register_instagram_publish_handlers",
    "run_instagram_publish",
]
