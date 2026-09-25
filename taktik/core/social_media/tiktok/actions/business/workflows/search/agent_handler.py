"""The one launcher of a TikTok Search or Hashtag run, and its Agent handlers.

`run_tiktok_search` is what the desktop bridge calls and what the handlers registered as
`tiktok.automation.search`, `.hashtag` and `.target` (the CLI) call. A run walks its queries in
order, shares the video budget between them, carries the like and follow budgets over from one
query to the next, and returns home between two queries. What differs between hosts is injected:
- `tiktok_startup() -> TikTokStartup`: clean restart, language, account; supplies the device.
- `tiktok_ai_hooks(ai_config, language)`: installs the AI hooks the run asks for.
- `query_hook(workflow, query)`: wires the live events of one query; defaults to `notifier`.
- `on_finished(totals)`: reports the end of the run.
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from loguru import logger

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    attach_video_callbacks,
    merge_invocation_payload,
)
from taktik.core.social_media.tiktok.actions.business.workflows._internal.models import VideoWorkflowStats
from taktik.core.social_media.tiktok.actions.business.workflows._internal.video_payload import (
    video_settings_from_payload,
)
from taktik.core.social_media.tiktok.actions.business.workflows.search.payload import (
    query_label,
    search_config_for_query,
    search_queries_from_payload,
)


TIKTOK_SEARCH_WORKFLOW_ID = "tiktok.automation.search"
TIKTOK_HASHTAG_WORKFLOW_ID = "tiktok.automation.hashtag"
TIKTOK_TARGET_WORKFLOW_ID = "tiktok.automation.target"
TIKTOK_SEARCH_WORKFLOW_IDS = (
    TIKTOK_SEARCH_WORKFLOW_ID,
    TIKTOK_HASHTAG_WORKFLOW_ID,
    TIKTOK_TARGET_WORKFLOW_ID,
)
SearchWorkflowFactory = Callable[..., Any]
StartupProvider = Callable[[], Any]
AIHooks = Callable[[Any, str], None]
FinishedHook = Callable[[VideoWorkflowStats], None]

# Counters a session adds up across its queries.
_SUMMED_COUNTERS = (
    "videos_watched", "videos_liked", "users_followed", "videos_favorited", "videos_commented",
    "videos_reposted", "videos_rejected", "videos_skipped", "ads_skipped", "lives_skipped",
    "popups_closed", "suggestions_handled", "errors",
)


@dataclass
class SearchQuery:
    """One query of a session, as a host sees it when its workflow is about to run."""

    index: int
    query: str
    queries: list[str]
    workflow_type: str
    #: The session's totals before this query.
    totals: VideoWorkflowStats

    @property
    def label(self) -> str:
        return query_label(self.query, self.workflow_type)


QueryHook = Callable[[Any, SearchQuery], None]


def _default_workflow_factory() -> SearchWorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.tiktok.actions.business.workflows.search import workflow

    return workflow.SearchWorkflow


def _return_home(device) -> None:
    from taktik.core.social_media.tiktok.services.navigation import reset

    reset.return_to_tiktok_home(device, logger=logger)


def run_tiktok_search(
    payload: Any,
    *,
    workflow_type: str = "search",
    device=None,
    notifier=None,
    workflow_factory: Optional[SearchWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
    query_hook: Optional[QueryHook] = None,
    on_finished: Optional[FinishedHook] = None,
) -> dict[str, Any]:
    """Start, hook and run every query of one Search or Hashtag session from a payload."""
    from taktik.core.social_media.tiktok.workflows.core.ai_hooks import (
        ai_config_from_payload,
        app_language_from_payload,
    )

    queries = search_queries_from_payload(payload, hashtag=workflow_type == "hashtag")
    if not queries:
        raise ValueError("TikTok search requires a non-empty searchQuery")

    run_device = device
    if tiktok_startup is not None:
        run_device = tiktok_startup().device

    if tiktok_ai_hooks is not None:
        tiktok_ai_hooks(ai_config_from_payload(payload), app_language_from_payload(payload))

    settings = video_settings_from_payload(payload)
    videos_per_query, extra_videos = divmod(settings["max_videos"], len(queries))
    remaining_likes = settings["max_likes_per_session"]
    remaining_follows = settings["max_follows_per_session"]
    totals = VideoWorkflowStats()
    factory = workflow_factory or _default_workflow_factory()

    for index, query in enumerate(queries):
        if remaining_likes <= 0 and remaining_follows <= 0:
            logger.info("Session limits reached, skipping remaining queries")
            break

        query_max_videos = videos_per_query + (1 if index < extra_videos else 0)
        if query_max_videos <= 0:
            logger.info("No remaining video budget for this query, skipping it")
            continue

        context = SearchQuery(index=index, query=query, queries=queries, workflow_type=workflow_type,
                              totals=totals)
        logger.info(f"Processing query {index + 1}/{len(queries)}: {context.label}")
        logger.info(f"Max videos for this query: {query_max_videos}")

        config = search_config_for_query(
            settings,
            search_query=query,
            max_videos=query_max_videos,
            max_likes_per_session=remaining_likes,
            max_follows_per_session=remaining_follows,
        )
        workflow = factory(run_device, config)
        if query_hook is not None:
            query_hook(workflow, context)
        else:
            attach_video_callbacks(workflow, notifier)

        logger.info("Running search workflow...")
        stats = workflow.run()
        for counter in _SUMMED_COUNTERS:
            setattr(totals, counter, getattr(totals, counter) + getattr(stats, counter, 0))
        remaining_likes = max(0, remaining_likes - stats.videos_liked)
        remaining_follows = max(0, remaining_follows - stats.users_followed)
        logger.info(
            f"Query {context.label} completed: "
            f"{stats.videos_watched} videos, {stats.videos_liked} likes, {stats.users_followed} follows"
        )

        if index < len(queries) - 1:
            _return_home(run_device)

    if on_finished is not None:
        on_finished(totals)
    return {"success": True, "queries": queries, "stats": totals.to_dict()}


def build_tiktok_search_handler(
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[SearchWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
) -> WorkflowHandler:
    """Build the Search/Hashtag/Target handler for the Agent runtime."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        return run_tiktok_search(
            merge_invocation_payload(invocation, payload),
            workflow_type=invocation.workflow_id.rsplit(".", 1)[-1],
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
            tiktok_ai_hooks=tiktok_ai_hooks,
        )

    return handler


def register_tiktok_search_handlers(
    registry: WorkflowRegistry,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[SearchWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
) -> WorkflowRegistry:
    """Register TikTok Search/Hashtag/Target handlers into an injected registry."""
    handler = build_tiktok_search_handler(
        device=device,
        notifier=notifier,
        workflow_factory=workflow_factory,
        tiktok_startup=tiktok_startup,
        tiktok_ai_hooks=tiktok_ai_hooks,
    )
    for workflow_id in TIKTOK_SEARCH_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry
