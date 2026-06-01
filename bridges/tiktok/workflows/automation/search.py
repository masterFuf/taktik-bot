#!/usr/bin/env python3
"""
TikTok Search Bridge - Search/Hashtag workflow
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import (
    logger,
    send_error,
    send_status,
)
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.runtime.video_callbacks import send_final_video_stats
from bridges.tiktok.workflows.automation.runtime.search_callbacks import (
    return_to_tiktok_home,
)
from bridges.tiktok.workflows.automation.runtime.search_planning import (
    format_query_label,
    normalize_search_queries,
)
from bridges.tiktok.workflows.automation.runtime.search_query import run_search_query


def run_search_workflow(config: Dict[str, Any]):
    """Run the TikTok Search/Hashtag workflow."""
    device_id = config.get("deviceId")
    workflow_type = str(config.get("workflowType") or "search").strip().lower()
    search_queries = normalize_search_queries(config)

    if not device_id:
        send_error("No device ID provided")
        return False

    if not search_queries:
        send_error("No search query provided")
        return False

    logger.info(f"Starting TikTok Search workflow on device: {device_id}")
    logger.info(
        f"Search queries ({len(search_queries)}): "
        f"{', '.join(format_query_label(query, workflow_type) for query in search_queries)}"
    )
    send_status("starting", f"Initializing TikTok Search workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.search.workflow import (
            SearchConfig,
            SearchStats,
            SearchWorkflow,
        )

        manager, _bot_username = tiktok_startup(device_id, fetch_profile=True)

        max_videos_total = config.get("maxVideos", 50)
        videos_per_query = max_videos_total // len(search_queries)
        extra_videos = max_videos_total % len(search_queries)
        remaining_likes = config.get("maxLikesPerSession", 50)
        remaining_follows = config.get("maxFollowsPerSession", 20)
        total_stats = SearchStats()
        sent_pics: set = set()

        for query_index, search_query in enumerate(search_queries):
            if remaining_likes <= 0 and remaining_follows <= 0:
                logger.info("Session limits reached, skipping remaining queries")
                break

            query_max_videos = videos_per_query + (1 if query_index < extra_videos else 0)
            if query_max_videos <= 0:
                logger.info("No remaining video budget for this query, skipping it")
                continue
            query_result = run_search_query(
                SearchWorkflow,
                SearchConfig,
                manager,
                config,
                search_queries,
                query_index,
                search_query,
                workflow_type,
                query_max_videos,
                remaining_likes,
                remaining_follows,
                total_stats,
                sent_pics,
            )
            remaining_likes = query_result.remaining_likes
            remaining_follows = query_result.remaining_follows

            if query_index < len(search_queries) - 1:
                return_to_tiktok_home(manager)

        send_final_video_stats(total_stats, "Search workflow")
        return True

    except ImportError as exc:
        error_msg = f"Import error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as exc:
        error_msg = f"Search workflow error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
