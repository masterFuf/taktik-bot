"""Agent runtime handler for the TikTok Unfollow workflow."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    merge_invocation_payload,
    notify,
)
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.payload import (
    unfollow_config_from_payload,
)
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow import UnfollowWorkflow


TIKTOK_UNFOLLOW_WORKFLOW_ID = "tiktok.standalone.tiktok_unfollow"
UnfollowWorkflowFactory = Callable[..., Any]


def build_tiktok_unfollow_handler(
    *,
    device,
    notifier=None,
    workflow_factory: UnfollowWorkflowFactory = UnfollowWorkflow,
) -> WorkflowHandler:
    """Build an injectable unfollow handler for the Agent runtime."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = merge_invocation_payload(invocation, payload)
        workflow = workflow_factory(device, unfollow_config_from_payload(merged))
        _attach_callbacks(workflow, notifier, target=workflow.config.max_unfollows)
        stats = workflow.run()
        return {"success": True, "stats": stats.to_dict()}

    return handler


def register_tiktok_unfollow_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    notifier=None,
    workflow_factory: UnfollowWorkflowFactory = UnfollowWorkflow,
) -> WorkflowRegistry:
    """Register TikTok unfollow handlers into an injected Agent registry."""
    registry.register(
        TIKTOK_UNFOLLOW_WORKFLOW_ID,
        build_tiktok_unfollow_handler(
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
        ),
    )
    return registry


def _attach_callbacks(workflow: Any, notifier: Any, *, target: int) -> None:
    if notifier is None:
        return

    if hasattr(workflow, "set_on_unfollow_callback"):
        workflow.set_on_unfollow_callback(
            lambda username, count: notify(
                notifier,
                "unfollow_event",
                event="unfollowed",
                username=username,
                count=count,
            )
        )
    if hasattr(workflow, "set_on_skip_callback"):
        workflow.set_on_skip_callback(
            lambda username, reason="friends": notify(
                notifier,
                "unfollow_event",
                event="skipped",
                reason=reason,
                username=username,
            )
        )
    if hasattr(workflow, "set_on_unconfirmed_callback"):
        workflow.set_on_unconfirmed_callback(
            lambda username, state: notify(
                notifier,
                "unfollow_event",
                event="not_confirmed",
                reason="not_confirmed",
                state=state,
                username=username,
            )
        )
    if hasattr(workflow, "set_on_stats_callback"):
        workflow.set_on_stats_callback(
            lambda stats: notify(notifier, "unfollow_stats", stats={**stats, "target": target})
        )
