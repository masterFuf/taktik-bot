"""Agent runtime handler for TikTok Search/Hashtag/Target workflows."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
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
        merged = _merged(invocation, payload)
        workflow = workflow_factory(device, _search_config(invocation.workflow_id, merged))
        _attach_video_callbacks(workflow, notifier)
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
        max_videos=_int_param(payload, "max_videos", "maxVideos", default=50),
        min_watch_time=_float_param(payload, "min_watch_time", "minWatchTime", default=2.0),
        max_watch_time=_float_param(payload, "max_watch_time", "maxWatchTime", default=8.0),
        like_probability=_probability_param(payload, "like_probability", "likeProbability", default=0.3),
        follow_probability=_probability_param(
            payload, "follow_probability", "followProbability", default=0.1
        ),
        favorite_probability=_probability_param(
            payload, "favorite_probability", "favoriteProbability", default=0.05
        ),
        min_likes=_optional_int_param(payload, "min_likes", "minLikes"),
        max_likes=_optional_int_param(payload, "max_likes", "maxLikes"),
        max_likes_per_session=_int_param(
            payload, "max_likes_per_session", "maxLikesPerSession", default=50
        ),
        max_follows_per_session=_int_param(
            payload, "max_follows_per_session", "maxFollowsPerSession", default=20
        ),
        pause_after_actions=_int_param(payload, "pause_after_actions", "pauseAfterActions", default=10),
        pause_duration_min=_float_param(
            payload, "pause_duration_min", "pauseDurationMin", default=30.0
        ),
        pause_duration_max=_float_param(
            payload, "pause_duration_max", "pauseDurationMax", default=60.0
        ),
        skip_already_liked=_bool_param(
            payload, "skip_already_liked", "skipAlreadyLiked", default=True
        ),
        skip_already_followed=_bool_param(
            payload, "skip_already_followed", "skipAlreadyFollowed", default=True
        ),
        skip_ads=_bool_param(payload, "skip_ads", "skipAds", default=True),
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


def _attach_video_callbacks(workflow: Any, notifier: Any) -> None:
    if notifier is None:
        return

    if hasattr(workflow, "set_on_video_callback"):
        workflow.set_on_video_callback(lambda video: _notify(notifier, "video_info", video=video))
    if hasattr(workflow, "set_on_like_callback"):
        workflow.set_on_like_callback(
            lambda video: _notify(notifier, "action", action="like", target=video.get("author", ""))
        )
    if hasattr(workflow, "set_on_follow_callback"):
        workflow.set_on_follow_callback(
            lambda video: _notify(notifier, "action", action="follow", target=video.get("author", ""))
        )
    if hasattr(workflow, "set_on_stats_callback"):
        workflow.set_on_stats_callback(lambda stats: _notify(notifier, "tiktok_stats", stats=stats))
    if hasattr(workflow, "set_on_pause_callback"):
        workflow.set_on_pause_callback(lambda duration: _notify(notifier, "pause", duration=duration))


def _notify(notifier: Any, event_type: str, **payload: Any) -> None:
    sender = getattr(notifier, "send", None)
    if callable(sender):
        sender(event_type, **payload)
        return
    method = getattr(notifier, event_type, None)
    if callable(method):
        method(**payload)


def _merged(invocation: WorkflowInvocation, payload: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(payload)
    merged.update(invocation.params)
    return merged


def _int_param(payload: Mapping[str, Any], *names: str, default: int) -> int:
    return int(_value(payload, *names, default=default))


def _optional_int_param(payload: Mapping[str, Any], *names: str) -> int | None:
    value = _value(payload, *names, default=None)
    return int(value) if value is not None else None


def _float_param(payload: Mapping[str, Any], *names: str, default: float) -> float:
    return float(_value(payload, *names, default=default))


def _probability_param(payload: Mapping[str, Any], *names: str, default: float) -> float:
    value = float(_value(payload, *names, default=default))
    return value / 100.0 if value > 1 else value


def _bool_param(payload: Mapping[str, Any], *names: str, default: bool) -> bool:
    value = _value(payload, *names, default=default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _value(payload: Mapping[str, Any], *names: str, default: Any) -> Any:
    for name in names:
        value = payload.get(name)
        if value is not None:
            return value
    return default
