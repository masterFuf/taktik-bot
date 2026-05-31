"""Agent runtime handlers for Threads workflows."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.threads.workflows.feed_and_interact import (
    FeedInteractConfig,
    run_feed_and_interact,
)
from taktik.core.social_media.threads.workflows.search_and_interact import (
    ActionProbabilities,
    ProfileFilters,
    SearchInteractConfig,
    run_search_and_interact,
)


THREADS_FOLLOW_WORKFLOW_ID = "threads.automation.follow"
THREADS_TARGET_WORKFLOW_ID = "threads.automation.target"
THREADS_FEED_WORKFLOW_ID = "threads.automation.feed"
THREADS_AUTOMATION_WORKFLOW_IDS = (
    THREADS_FOLLOW_WORKFLOW_ID,
    THREADS_TARGET_WORKFLOW_ID,
    THREADS_FEED_WORKFLOW_ID,
)
StartupProvider = Callable[[WorkflowInvocation, Mapping[str, Any]], Any]
SearchRunner = Callable[..., Any]
FeedRunner = Callable[..., Any]


def build_threads_automation_handler(
    *,
    startup_provider: StartupProvider,
    search_runner: SearchRunner = run_search_and_interact,
    feed_runner: FeedRunner = run_feed_and_interact,
    on_log=None,
    on_stats=None,
    on_profile_visit=None,
    on_action=None,
) -> WorkflowHandler:
    """Build Threads handlers with startup supplied by the caller."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = dict(payload)
        merged.update(invocation.params)
        startup = startup_provider(invocation, merged)
        if startup is None:
            raise ValueError("Threads Agent handler requires injected startup")

        if invocation.workflow_id == THREADS_FEED_WORKFLOW_ID:
            stats = feed_runner(
                _feed_config(merged),
                on_log=on_log,
                on_stats=on_stats,
                on_profile_visit=on_profile_visit,
                on_action=on_action,
                startup=startup,
            )
        elif invocation.workflow_id in {THREADS_FOLLOW_WORKFLOW_ID, THREADS_TARGET_WORKFLOW_ID}:
            stats = search_runner(
                _search_config(merged),
                on_log=on_log,
                on_stats=on_stats,
                on_profile_visit=on_profile_visit,
                on_action=on_action,
                startup=startup,
            )
        else:
            raise ValueError(f"Unsupported Threads workflow id: {invocation.workflow_id}")

        return {"success": True, "stats": stats.as_dict()}

    return handler


def register_threads_automation_handlers(
    registry: WorkflowRegistry,
    *,
    startup_provider: StartupProvider,
    search_runner: SearchRunner = run_search_and_interact,
    feed_runner: FeedRunner = run_feed_and_interact,
    on_log=None,
    on_stats=None,
    on_profile_visit=None,
    on_action=None,
) -> WorkflowRegistry:
    """Register Threads automation handlers into an injected Agent registry."""
    handler = build_threads_automation_handler(
        startup_provider=startup_provider,
        search_runner=search_runner,
        feed_runner=feed_runner,
        on_log=on_log,
        on_stats=on_stats,
        on_profile_visit=on_profile_visit,
        on_action=on_action,
    )
    for workflow_id in THREADS_AUTOMATION_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _search_config(payload: Mapping[str, Any]) -> SearchInteractConfig:
    query = _string_param(payload, "searchQuery", "search_query", "target", "username", default="")
    if not query:
        targets = _value_param(payload, "targets", "targetAccounts")
        if isinstance(targets, str):
            query = targets.strip().lstrip("@")
        elif isinstance(targets, list) and targets:
            query = str(targets[0]).strip().lstrip("@")
    if not query:
        raise ValueError("Threads follow/target workflow requires searchQuery or target")

    return SearchInteractConfig(
        device_id=_string_param(payload, "deviceId", "device_id", default="agent"),
        search_query=query,
        max_profiles=_int_param(payload, "maxProfiles", "maxFollows", default=10),
        min_delay_seconds=_float_param(payload, "minDelaySeconds", default=2.0),
        max_delay_seconds=_float_param(payload, "maxDelaySeconds", default=5.0),
        max_likes_per_profile=_int_param(payload, "maxLikesPerProfile", default=2),
        actions=_actions(payload),
        filters=_filters(payload),
    )


def _feed_config(payload: Mapping[str, Any]) -> FeedInteractConfig:
    return FeedInteractConfig(
        device_id=_string_param(payload, "deviceId", "device_id", default="agent"),
        max_profiles=_int_param(payload, "maxProfiles", "maxFollows", default=10),
        min_delay_seconds=_float_param(payload, "minDelaySeconds", default=2.0),
        max_delay_seconds=_float_param(payload, "maxDelaySeconds", default=5.0),
        max_likes_per_profile=_int_param(payload, "maxLikesPerProfile", default=2),
        actions=_actions(payload),
        filters=_filters(payload),
    )


def _actions(payload: Mapping[str, Any]) -> ActionProbabilities:
    action_cfg = _mapping_param(payload, "actionProbabilities", "actions")
    return ActionProbabilities(
        follow=int(action_cfg.get("follow", 80)),
        like=int(action_cfg.get("like", 50)),
        repost=int(action_cfg.get("repost", 0)),
        comment=int(action_cfg.get("comment", 0)),
    )


def _filters(payload: Mapping[str, Any]) -> ProfileFilters:
    filters_cfg = _mapping_param(payload, "filters")
    return ProfileFilters(
        min_followers=int(filters_cfg.get("minFollowers", 0)),
        max_followers=int(filters_cfg.get("maxFollowers", 10_000_000)),
        bio_keywords_include=list(filters_cfg.get("bioKeywordsInclude") or []),
        bio_keywords_exclude=list(filters_cfg.get("bioKeywordsExclude") or []),
    )


def _value_param(payload: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return None


def _mapping_param(payload: Mapping[str, Any], *names: str) -> dict[str, Any]:
    value = _value_param(payload, *names)
    return dict(value) if isinstance(value, Mapping) else {}


def _string_param(payload: Mapping[str, Any], *names: str, default: str) -> str:
    value = _value_param(payload, *names)
    if value is None:
        return default
    return str(value).strip() or default


def _int_param(payload: Mapping[str, Any], *names: str, default: int) -> int:
    value = _value_param(payload, *names)
    if value is None:
        return default
    return int(value)


def _float_param(payload: Mapping[str, Any], *names: str, default: float) -> float:
    value = _value_param(payload, *names)
    if value is None:
        return default
    return float(value)
