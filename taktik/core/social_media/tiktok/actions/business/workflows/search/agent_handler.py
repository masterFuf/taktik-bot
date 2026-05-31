"""Agent runtime handler for TikTok Search/Hashtag/Target workflows."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    attach_video_callbacks,
    bool_param,
    float_param,
    int_param,
    merge_invocation_payload,
    optional_int_param,
    probability_param,
)
from taktik.core.social_media.tiktok.actions.business.workflows.search.models import SearchConfig
from taktik.core.social_media.tiktok.actions.business.workflows.search.workflow import SearchWorkflow


TIKTOK_SEARCH_WORKFLOW_ID = "tiktok.automation.search"
TIKTOK_HASHTAG_WORKFLOW_ID = "tiktok.automation.hashtag"
TIKTOK_TARGET_WORKFLOW_ID = "tiktok.automation.target"
TIKTOK_SEARCH_WORKFLOW_IDS = (
    TIKTOK_SEARCH_WORKFLOW_ID,
    TIKTOK_HASHTAG_WORKFLOW_ID,
    TIKTOK_TARGET_WORKFLOW_ID,
)
SearchWorkflowFactory = Callable[..., Any]


def build_tiktok_search_handler(
    *,
    device,
    notifier=None,
    workflow_factory: SearchWorkflowFactory = SearchWorkflow,
) -> WorkflowHandler:
    """Build a single-query Search handler for the Agent runtime."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = merge_invocation_payload(invocation, payload)
        workflow = workflow_factory(device, _search_config(invocation.workflow_id, merged))
        attach_video_callbacks(workflow, notifier)
        stats = workflow.run()
        return {"success": True, "stats": stats.to_dict()}

    return handler


def register_tiktok_search_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    notifier=None,
    workflow_factory: SearchWorkflowFactory = SearchWorkflow,
) -> WorkflowRegistry:
    """Register TikTok Search/Hashtag/Target handlers into an injected registry."""
    handler = build_tiktok_search_handler(
        device=device,
        notifier=notifier,
        workflow_factory=workflow_factory,
    )
    for workflow_id in TIKTOK_SEARCH_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _search_config(workflow_id: str, payload: Mapping[str, Any]) -> SearchConfig:
    query = _query_param(workflow_id, payload)
    if not query:
        raise ValueError("TikTok search requires a non-empty searchQuery")

    return SearchConfig(
        search_query=query,
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
    )


def _query_param(workflow_id: str, payload: Mapping[str, Any]) -> str:
    value = (
        payload.get("search_query")
        or payload.get("searchQuery")
        or payload.get("target")
        or payload.get("username")
        or payload.get("hashtag")
    )
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    query = str(value or "").strip()
    if workflow_id == TIKTOK_HASHTAG_WORKFLOW_ID:
        query = query.lstrip("#")
    return query
