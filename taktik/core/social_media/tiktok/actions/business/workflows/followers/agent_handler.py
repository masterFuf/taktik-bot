"""Agent runtime handler for the TikTok Followers workflow."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
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
        merged = _merged(invocation, payload)
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
        max_followers=_int_param(merged, "max_followers", "maxFollowers", "maxVideos", default=50),
        posts_per_profile=_int_param(merged, "posts_per_profile", "postsPerProfile", default=2),
        min_watch_time=_float_param(merged, "min_watch_time", "minWatchTime", default=5.0),
        max_watch_time=_float_param(merged, "max_watch_time", "maxWatchTime", default=15.0),
        like_probability=_probability_param(merged, "like_probability", "likeProbability", default=0.7),
        comment_probability=_probability_param(
            merged, "comment_probability", "commentProbability", default=0.1
        ),
        share_probability=_probability_param(merged, "share_probability", "shareProbability", default=0.05),
        favorite_probability=_probability_param(
            merged, "favorite_probability", "favoriteProbability", default=0.3
        ),
        follow_probability=_probability_param(merged, "follow_probability", "followProbability", default=0.5),
        story_like_probability=_probability_param(
            merged, "story_like_probability", "storyLikeProbability", default=0.5
        ),
        max_likes_per_session=_int_param(
            merged, "max_likes_per_session", "maxLikesPerSession", default=50
        ),
        max_follows_per_session=_int_param(
            merged, "max_follows_per_session", "maxFollowsPerSession", default=20
        ),
        max_comments_per_session=_int_param(
            merged, "max_comments_per_session", "maxCommentsPerSession", default=10
        ),
        min_delay=_float_param(merged, "min_delay", "minDelay", default=1.0),
        max_delay=_float_param(merged, "max_delay", "maxDelay", default=3.0),
        pause_after_actions=_int_param(merged, "pause_after_actions", "pauseAfterActions", default=10),
        pause_duration_min=_float_param(
            merged, "pause_duration_min", "pauseDurationMin", default=30.0
        ),
        pause_duration_max=_float_param(
            merged, "pause_duration_max", "pauseDurationMax", default=60.0
        ),
        include_friends=_bool_param(merged, "include_friends", "includeFriends", default=False),
        skip_private_accounts=_bool_param(
            merged, "skip_private_accounts", "skipPrivateAccounts", default=False
        ),
        max_consecutive_known_usernames=_int_param(
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
        workflow.set_on_stats_callback(lambda stats: _notify(notifier, "followers_stats", stats=stats))
    if hasattr(workflow, "set_on_action_callback"):
        workflow.set_on_action_callback(
            lambda action: _notify(
                notifier,
                "action",
                action=action.get("action", "unknown"),
                target=action.get("target", ""),
            )
        )
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
