"""Agent runtime handler for the TikTok For You workflow."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    attach_video_callbacks,
    bool_param,
    float_param,
    int_param,
    list_param,
    merge_invocation_payload,
    optional_int_param,
    probability_param,
)
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.models import ForYouConfig
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.workflow import ForYouWorkflow


TIKTOK_FOR_YOU_WORKFLOW_ID = "tiktok.automation.for_you"
ForYouWorkflowFactory = Callable[..., Any]


def build_tiktok_for_you_handler(
    *,
    device,
    notifier=None,
    workflow_factory: ForYouWorkflowFactory = ForYouWorkflow,
) -> WorkflowHandler:
    """Build an injectable For You handler for the Agent runtime."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = merge_invocation_payload(invocation, payload)
        workflow = workflow_factory(device, _for_you_config(merged))
        attach_video_callbacks(workflow, notifier)
        stats = workflow.run()
        return {"success": True, "stats": stats.to_dict()}

    return handler


def register_tiktok_for_you_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    notifier=None,
    workflow_factory: ForYouWorkflowFactory = ForYouWorkflow,
) -> WorkflowRegistry:
    """Register TikTok For You handlers into an injected Agent registry."""
    registry.register(
        TIKTOK_FOR_YOU_WORKFLOW_ID,
        build_tiktok_for_you_handler(
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
        ),
    )
    return registry


def _for_you_config(payload: Mapping[str, Any]) -> ForYouConfig:
    return ForYouConfig(
        max_videos=int_param(payload, "max_videos", "maxVideos", default=50),
        min_watch_time=float_param(payload, "min_watch_time", "minWatchTime", default=2.0),
        max_watch_time=float_param(payload, "max_watch_time", "maxWatchTime", default=8.0),
        like_probability=probability_param(payload, "like_probability", "likeProbability", default=0.3),
        follow_probability=probability_param(
            payload, "follow_probability", "followProbability", default=0.1
        ),
        favorite_probability=probability_param(
            payload, "favorite_probability", "favoriteProbability", default=0.05
        ),
        required_hashtags=list_param(payload, "required_hashtags", "requiredHashtags"),
        excluded_hashtags=list_param(payload, "excluded_hashtags", "excludedHashtags"),
        min_likes=optional_int_param(payload, "min_likes", "minLikes"),
        max_likes=optional_int_param(payload, "max_likes", "maxLikes"),
        max_likes_per_session=int_param(
            payload, "max_likes_per_session", "maxLikesPerSession", default=50
        ),
        max_follows_per_session=int_param(
            payload, "max_follows_per_session", "maxFollowsPerSession", default=20
        ),
        pause_after_actions=int_param(payload, "pause_after_actions", "pauseAfterActions", default=10),
        pause_duration_min=float_param(
            payload, "pause_duration_min", "pauseDurationMin", default=30.0
        ),
        pause_duration_max=float_param(
            payload, "pause_duration_max", "pauseDurationMax", default=60.0
        ),
        skip_already_liked=bool_param(
            payload, "skip_already_liked", "skipAlreadyLiked", default=True
        ),
        skip_already_followed=bool_param(
            payload, "skip_already_followed", "skipAlreadyFollowed", default=True
        ),
        skip_ads=bool_param(payload, "skip_ads", "skipAds", default=True),
        follow_back_suggestions=bool_param(
            payload, "follow_back_suggestions", "followBackSuggestions", default=False
        ),
    )
