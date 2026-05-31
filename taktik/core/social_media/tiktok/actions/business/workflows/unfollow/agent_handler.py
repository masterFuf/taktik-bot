"""Agent runtime handler for the TikTok Unfollow workflow."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    bool_param,
    float_param,
    int_param,
    merge_invocation_payload,
    notify,
)
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.models import UnfollowConfig
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
        workflow = workflow_factory(device, _unfollow_config(merged))
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


def _unfollow_config(payload: Mapping[str, Any]) -> UnfollowConfig:
    include_friends = bool_param(payload, "include_friends", "includeFriends", default=False)
    skip_friends_value = (
        payload.get("skipFriends") if "skipFriends" in payload else payload.get("skip_friends")
    )
    if skip_friends_value is not None:
        include_friends = not bool_param(payload, "skip_friends", "skipFriends", default=True)

    return UnfollowConfig(
        max_unfollows=int_param(payload, "max_unfollows", "maxUnfollows", default=20),
        include_friends=include_friends,
        min_delay=float_param(payload, "min_delay", "minDelay", default=1.0),
        max_delay=float_param(payload, "max_delay", "maxDelay", default=3.0),
        max_scroll_attempts=int_param(
            payload, "max_scroll_attempts", "maxScrollAttempts", default=10
        ),
    )


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
            lambda username: notify(
                notifier,
                "unfollow_event",
                event="skipped",
                reason="friends",
                username=username,
            )
        )
    if hasattr(workflow, "set_on_stats_callback"):
        workflow.set_on_stats_callback(
            lambda stats: notify(notifier, "unfollow_stats", stats={**stats, "target": target})
        )
