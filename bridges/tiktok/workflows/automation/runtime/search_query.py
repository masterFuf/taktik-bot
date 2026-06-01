"""Single-query execution for the TikTok Search/Hashtag bridge runner."""

from dataclasses import dataclass
from typing import Any, Dict, List, Type

from bridges.tiktok.runtime.ipc import logger, send_message, send_status, set_workflow
from bridges.tiktok.workflows.automation.runtime.search_callbacks import (
    setup_search_workflow_callbacks,
)
from bridges.tiktok.workflows.automation.runtime.search_config import build_search_config
from bridges.tiktok.workflows.automation.runtime.search_planning import format_query_label


@dataclass
class SearchQueryResult:
    """Result of one query pass in a multi-query Search/Hashtag session."""

    remaining_likes: int
    remaining_follows: int


def run_search_query(
    search_workflow_class: Type[Any],
    search_config_class: Type[Any],
    manager: Any,
    config: Dict[str, Any],
    search_queries: List[str],
    query_index: int,
    search_query: str,
    workflow_type: str,
    query_max_videos: int,
    remaining_likes: int,
    remaining_follows: int,
    total_stats: Any,
    sent_pics: set,
) -> SearchQueryResult:
    """Run the Search workflow for one query and update aggregate stats."""
    display_query = format_query_label(search_query, workflow_type)

    logger.info(f"Processing query {query_index + 1}/{len(search_queries)}: {display_query}")
    logger.info(f"Max videos for this query: {query_max_videos}")

    if query_index == 0:
        send_message(
            "search_workflow_start",
            current_target=search_query,
            targets=search_queries,
            current_target_index=query_index,
            workflow_type=workflow_type,
        )
    else:
        send_message(
            "search_target_switch",
            current_target=search_query,
            target_index=query_index,
            total_targets=len(search_queries),
            workflow_type=workflow_type,
        )

    workflow_config = build_search_config(
        search_config_class,
        config,
        search_query,
        query_max_videos,
        remaining_likes,
        remaining_follows,
    )

    send_status("running", f"Searching for: {display_query}")
    workflow = search_workflow_class(manager.device_manager.device, workflow_config)
    set_workflow(workflow)
    setup_search_workflow_callbacks(
        workflow,
        {
            "videos_watched": total_stats.videos_watched,
            "videos_liked": total_stats.videos_liked,
            "users_followed": total_stats.users_followed,
            "videos_favorited": total_stats.videos_favorited,
            "videos_skipped": total_stats.videos_skipped,
            "errors": total_stats.errors,
        },
        sent_pics,
    )

    logger.info("Running search workflow...")
    stats = workflow.run()

    total_stats.videos_watched += stats.videos_watched
    total_stats.videos_liked += stats.videos_liked
    total_stats.users_followed += stats.users_followed
    total_stats.videos_favorited += stats.videos_favorited
    total_stats.videos_skipped += stats.videos_skipped
    total_stats.ads_skipped += stats.ads_skipped
    total_stats.popups_closed += stats.popups_closed
    total_stats.suggestions_handled += stats.suggestions_handled
    total_stats.errors += stats.errors

    next_remaining_likes = max(0, remaining_likes - stats.videos_liked)
    next_remaining_follows = max(0, remaining_follows - stats.users_followed)

    logger.info(
        f"Query {display_query} completed: "
        f"{stats.videos_watched} videos, {stats.videos_liked} likes, {stats.users_followed} follows"
    )

    return SearchQueryResult(
        remaining_likes=next_remaining_likes,
        remaining_follows=next_remaining_follows,
    )
