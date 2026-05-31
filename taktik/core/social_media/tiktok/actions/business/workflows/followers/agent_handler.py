"""Agent runtime handler for the TikTok Followers workflow."""

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
    probability_param,
)
from taktik.core.social_media.tiktok.actions.business.workflows.followers.models import FollowersConfig
from taktik.core.social_media.tiktok.actions.business.workflows.followers.workflow import FollowersWorkflow


TIKTOK_FOLLOWERS_WORKFLOW_ID = "tiktok.automation.followers"
FollowersWorkflowFactory = Callable[..., Any]


def build_tiktok_followers_handler(
    *,
    device,
    notifier=None,
    workflow_factory: FollowersWorkflowFactory = FollowersWorkflow,
) -> WorkflowHandler:
    """Build a single-target followers handler for the Agent runtime."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = merge_invocation_payload(invocation, payload)
        config = _followers_config(merged)
        bot_username = merged.get("botUsername") or merged.get("bot_username")
        workflow = workflow_factory(device, config)
        _attach_callbacks(workflow, notifier)
        stats = workflow.run(bot_username=str(bot_username) if bot_username else None)
        return {"success": True, "stats": stats.to_dict()}

    return handler


def register_tiktok_followers_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    notifier=None,
    workflow_factory: FollowersWorkflowFactory = FollowersWorkflow,
) -> WorkflowRegistry:
    """Register TikTok followers handlers into an injected Agent registry."""
    registry.register(
        TIKTOK_FOLLOWERS_WORKFLOW_ID,
        build_tiktok_followers_handler(
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
        ),
    )
    return registry


def _followers_config(merged: Mapping[str, Any]) -> FollowersConfig:
    target = (
        merged.get("search_query")
        or merged.get("searchQuery")
        or merged.get("target")
        or merged.get("username")
    )
    if not isinstance(target, str) or not target.strip():
        raise ValueError("TikTok followers requires a non-empty searchQuery")

    return FollowersConfig(
        search_query=target.strip().lstrip("@"),
        max_followers=int_param(merged, "max_followers", "maxFollowers", "maxVideos", default=50),
        posts_per_profile=int_param(merged, "posts_per_profile", "postsPerProfile", default=2),
        min_watch_time=float_param(merged, "min_watch_time", "minWatchTime", default=5.0),
        max_watch_time=float_param(merged, "max_watch_time", "maxWatchTime", default=15.0),
        like_probability=probability_param(merged, "like_probability", "likeProbability", default=0.7),
        comment_probability=probability_param(
            merged, "comment_probability", "commentProbability", default=0.1
        ),
        share_probability=probability_param(merged, "share_probability", "shareProbability", default=0.05),
        favorite_probability=probability_param(
            merged, "favorite_probability", "favoriteProbability", default=0.3
        ),
        follow_probability=probability_param(merged, "follow_probability", "followProbability", default=0.5),
        story_like_probability=probability_param(
            merged, "story_like_probability", "storyLikeProbability", default=0.5
        ),
        max_likes_per_session=int_param(
            merged, "max_likes_per_session", "maxLikesPerSession", default=50
        ),
        max_follows_per_session=int_param(
            merged, "max_follows_per_session", "maxFollowsPerSession", default=20
        ),
        max_comments_per_session=int_param(
            merged, "max_comments_per_session", "maxCommentsPerSession", default=10
        ),
        min_delay=float_param(merged, "min_delay", "minDelay", default=1.0),
        max_delay=float_param(merged, "max_delay", "maxDelay", default=3.0),
        pause_after_actions=int_param(merged, "pause_after_actions", "pauseAfterActions", default=10),
        pause_duration_min=float_param(
            merged, "pause_duration_min", "pauseDurationMin", default=30.0
        ),
        pause_duration_max=float_param(
            merged, "pause_duration_max", "pauseDurationMax", default=60.0
        ),
        include_friends=bool_param(merged, "include_friends", "includeFriends", default=False),
        skip_private_accounts=bool_param(
            merged, "skip_private_accounts", "skipPrivateAccounts", default=False
        ),
        max_consecutive_known_usernames=int_param(
            merged,
            "max_consecutive_known_usernames",
            "maxConsecutiveKnownUsernames",
            default=150,
        ),
    )


def _attach_callbacks(workflow: Any, notifier: Any) -> None:
    if notifier is None:
        return

    if hasattr(workflow, "set_on_stats_callback"):
        workflow.set_on_stats_callback(lambda stats: notify(notifier, "followers_stats", stats=stats))
    if hasattr(workflow, "set_on_action_callback"):
        workflow.set_on_action_callback(
            lambda action: notify(
                notifier,
                "action",
                action=action.get("action", "unknown"),
                target=action.get("target", ""),
            )
        )
    if hasattr(workflow, "set_on_pause_callback"):
        workflow.set_on_pause_callback(lambda duration: notify(notifier, "pause", duration=duration))
