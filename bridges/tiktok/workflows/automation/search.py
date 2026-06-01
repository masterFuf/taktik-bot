#!/usr/bin/env python3
"""
TikTok Search Bridge - Search/Hashtag workflow
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import (
    logger,
    send_error,
    send_message,
    send_status,
    set_workflow,
)
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.runtime.video_callbacks import send_final_video_stats
from bridges.tiktok.workflows.automation.runtime.search_callbacks import (
    return_to_tiktok_home,
    setup_search_workflow_callbacks,
)
from bridges.tiktok.workflows.automation.runtime.search_planning import (
    format_query_label,
    normalize_search_queries,
)


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

            workflow_config = SearchConfig(
                search_query=search_query,
                max_videos=query_max_videos,
                min_watch_time=config.get("minWatchTime", 2.0),
                max_watch_time=config.get("maxWatchTime", 8.0),
                like_probability=config.get("likeProbability", 30) / 100.0,
                follow_probability=config.get("followProbability", 10) / 100.0,
                favorite_probability=config.get("favoriteProbability", 5) / 100.0,
                min_likes=config.get("minLikes"),
                max_likes=config.get("maxLikes"),
                max_likes_per_session=remaining_likes,
                max_follows_per_session=remaining_follows,
                skip_already_liked=config.get("skipAlreadyLiked", True),
                skip_ads=config.get("skipAds", True),
                pause_after_actions=config.get("pauseAfterActions", 10),
                pause_duration_min=config.get("pauseDurationMin", 30.0),
                pause_duration_max=config.get("pauseDurationMax", 60.0),
            )

            send_status("running", f"Searching for: {display_query}")
            workflow = SearchWorkflow(manager.device_manager.device, workflow_config)
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

            remaining_likes = max(0, remaining_likes - stats.videos_liked)
            remaining_follows = max(0, remaining_follows - stats.users_followed)

            logger.info(
                f"Query {display_query} completed: "
                f"{stats.videos_watched} videos, {stats.videos_liked} likes, {stats.users_followed} follows"
            )

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
