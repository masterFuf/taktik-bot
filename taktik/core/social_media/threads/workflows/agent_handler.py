"""The launchers of the Threads runs, and their Agent handler.

`run_threads_search` (follow, target) and `run_threads_feed` are what the desktop bridge calls
and what the handler registered under the three `threads.automation.*` ids (the CLI) calls.
Both read the payload with the same readers below; what differs between hosts is injected:
- `startup`: an already started `(manager, device, anchor)`; without it the engine starts
  Threads itself from the payload's device id.
- `on_log`, `on_stats`, `on_profile_visit`, `on_action`: the live events.
- `on_started(config)`: reports the start, once the payload is read.
- `on_finished(stats)`: reports the end of the run.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

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
FinishedHook = Callable[[Any], None]
StartedHook = Callable[[Any], None]
LogHook = Callable[[str, str], None]


class ThreadsSearchQueryMissing(ValueError):
    """A follow/target run was given nothing to search for."""


# --------------------------------------------------------------------------- launchers


def run_threads_search(
    payload: Mapping[str, Any],
    *,
    startup=None,
    search_runner: SearchRunner = run_search_and_interact,
    on_log: Optional[LogHook] = None,
    on_stats=None,
    on_profile_visit=None,
    on_action=None,
    on_started: Optional[StartedHook] = None,
    on_finished: Optional[FinishedHook] = None,
) -> dict[str, Any]:
    """Read a follow/target payload, then run one Threads search-and-interact session."""
    config = threads_search_config_from_payload(payload)
    _announce(
        on_log,
        f"[threads:search] device={config.device_id} query={config.search_query!r} "
        f"max={config.max_profiles} {_probabilities(config.actions)}",
    )
    if on_started is not None:
        on_started(config)
    stats = search_runner(
        config,
        on_log=on_log,
        on_stats=on_stats,
        on_profile_visit=on_profile_visit,
        on_action=on_action,
        startup=startup,
    )
    return _finish(stats, on_finished)


def run_threads_feed(
    payload: Mapping[str, Any],
    *,
    startup=None,
    feed_runner: FeedRunner = run_feed_and_interact,
    on_log: Optional[LogHook] = None,
    on_stats=None,
    on_profile_visit=None,
    on_action=None,
    on_started: Optional[StartedHook] = None,
    on_finished: Optional[FinishedHook] = None,
) -> dict[str, Any]:
    """Read a feed payload, then run one Threads feed-and-interact session."""
    config = threads_feed_config_from_payload(payload)
    _announce(
        on_log,
        f"[threads:feed] device={config.device_id} max={config.max_profiles} "
        f"{_probabilities(config.actions)}",
    )
    if on_started is not None:
        on_started(config)
    stats = feed_runner(
        config,
        on_log=on_log,
        on_stats=on_stats,
        on_profile_visit=on_profile_visit,
        on_action=on_action,
        startup=startup,
    )
    return _finish(stats, on_finished)


def _succeeded(stats: Mapping[str, Any]) -> bool:
    """A run fails only when it hit errors and did nothing."""
    acted = int(stats.get("follows", 0)) + int(stats.get("likes", 0)) + int(stats.get("reposts", 0))
    return int(stats.get("errors", 0)) == 0 or acted > 0


def _finish(stats, on_finished: Optional[FinishedHook]) -> dict[str, Any]:
    if on_finished is not None:
        on_finished(stats)
    summary = stats.as_dict()
    return {"success": _succeeded(summary), "stats": summary}


def _announce(on_log: Optional[LogHook], message: str) -> None:
    if on_log is not None:
        on_log("info", message)


def _probabilities(actions: ActionProbabilities) -> str:
    return (
        f"probs(follow={actions.follow}% like={actions.like}% "
        f"repost={actions.repost}% comment={actions.comment}%)"
    )


# --------------------------------------------------------------------------- handler


def build_threads_automation_handler(
    *,
    startup_provider: Optional[StartupProvider] = None,
    search_runner: Optional[SearchRunner] = None,
    feed_runner: Optional[FeedRunner] = None,
    on_log=None,
    on_stats=None,
    on_profile_visit=None,
    on_action=None,
) -> WorkflowHandler:
    """Build Threads handlers with startup supplied by the caller."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = dict(payload)
        merged.update(invocation.params)
        # A provider is an option: without one, the engine starts Threads from the device id.
        startup = None
        if startup_provider is not None:
            startup = startup_provider(invocation, merged)
            if startup is None:
                raise ValueError("Threads Agent handler requires injected startup")

        events = {
            "startup": startup,
            "on_log": on_log,
            "on_stats": on_stats,
            "on_profile_visit": on_profile_visit,
            "on_action": on_action,
        }
        if invocation.workflow_id == THREADS_FEED_WORKFLOW_ID:
            if feed_runner is not None:
                events["feed_runner"] = feed_runner
            return run_threads_feed(merged, **events)
        if invocation.workflow_id in {THREADS_FOLLOW_WORKFLOW_ID, THREADS_TARGET_WORKFLOW_ID}:
            if search_runner is not None:
                events["search_runner"] = search_runner
            return run_threads_search(merged, **events)
        raise ValueError(f"Unsupported Threads workflow id: {invocation.workflow_id}")

    return handler


def register_threads_automation_handlers(
    registry: WorkflowRegistry,
    *,
    startup_provider: Optional[StartupProvider] = None,
    search_runner: Optional[SearchRunner] = None,
    feed_runner: Optional[FeedRunner] = None,
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


# --------------------------------------------------------------------------- payload


def threads_search_config_from_payload(payload: Mapping[str, Any]) -> SearchInteractConfig:
    """The follow/target settings, as the page, the scheduler and the CLI send them."""
    query = _string_param(payload, "searchQuery", "search_query", "target", "username", default="")
    if not query:
        for name in ("targets", "targetAccounts"):
            targets = payload.get(name)
            if isinstance(targets, str):
                targets = [targets]
            if isinstance(targets, list) and targets:
                query = str(targets[0]).strip().lstrip("@")
                break
    if not query:
        raise ThreadsSearchQueryMissing("Threads follow/target workflow requires searchQuery or target")

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


def threads_feed_config_from_payload(payload: Mapping[str, Any]) -> FeedInteractConfig:
    """The feed settings, as the page, the scheduler and the CLI send them."""
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
