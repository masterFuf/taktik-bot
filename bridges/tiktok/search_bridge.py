#!/usr/bin/env python3
"""
TikTok Search Bridge - Search/Hashtag workflow
"""

from typing import Any, Dict, List
import time

from .base import (
    logger,
    send_status,
    send_error,
    send_message,
    send_video_info,
    send_action,
    send_pause,
    send_stats,
    set_workflow,
    tiktok_startup,
    send_final_video_stats,
)


def _normalize_search_queries(config: Dict[str, Any]) -> List[str]:
    """Return a deduplicated list of queries.

    Hashtag workflows support the new `hashtags` array and fall back to the
    legacy `searchQuery` field for backward compatibility.
    """
    workflow_type = str(config.get("workflowType") or "").strip().lower()
    raw_queries = config.get("hashtags") or config.get("searchQueries") or []

    if isinstance(raw_queries, str):
        raw_queries = [raw_queries]

    queries: List[str] = []
    for raw_query in raw_queries:
        query = str(raw_query or "").strip()
        if workflow_type == "hashtag":
            query = query.lstrip("#")
        if query and query not in queries:
            queries.append(query)

    if queries:
        return queries

    single_query = str(config.get("searchQuery") or "").strip()
    if workflow_type == "hashtag":
        single_query = single_query.lstrip("#")

    return [single_query] if single_query else []


def _format_query_label(query: str, workflow_type: str) -> str:
    return f"#{query}" if workflow_type == "hashtag" else query


def _setup_search_workflow_callbacks(workflow, aggregate_stats: Dict[str, int], sent_pics: set):
    """Wire IPC callbacks while keeping session stats aggregated across queries."""

    def on_video(video_info):
        author = video_info.get("author", "unknown")

        author_pic = None
        if author and author not in sent_pics:
            try:
                detector = getattr(workflow, "detection", None) or getattr(workflow, "detector", None)
                if detector and hasattr(detector, "get_author_profile_pic"):
                    author_pic = detector.get_author_profile_pic()
                    if author_pic:
                        sent_pics.add(author)
            except Exception as exc:
                logger.debug(f"Could not capture profile pic for @{author}: {exc}")

        send_video_info(
            author=author,
            description=video_info.get("description"),
            like_count=video_info.get("like_count"),
            is_liked=video_info.get("is_liked", False),
            is_followed=video_info.get("is_followed", False),
            is_ad=video_info.get("is_ad", False),
            hashtags=video_info.get("hashtags") or [],
            sound=video_info.get("sound"),
            author_pic=author_pic,
        )

    def on_like(video_info):
        send_action("like", video_info.get("author", "unknown"))
        logger.info(f"Liked video by @{video_info.get('author', 'unknown')}")

    def on_follow(video_info):
        send_action("follow", video_info.get("author", "unknown"))
        logger.info(f"Followed @{video_info.get('author', 'unknown')}")

    def on_stats(stats_dict):
        send_stats(
            videos_watched=aggregate_stats["videos_watched"] + stats_dict.get("videos_watched", 0),
            videos_liked=aggregate_stats["videos_liked"] + stats_dict.get("videos_liked", 0),
            users_followed=aggregate_stats["users_followed"] + stats_dict.get("users_followed", 0),
            videos_favorited=aggregate_stats["videos_favorited"] + stats_dict.get("videos_favorited", 0),
            videos_skipped=aggregate_stats["videos_skipped"] + stats_dict.get("videos_skipped", 0),
            errors=aggregate_stats["errors"] + stats_dict.get("errors", 0),
        )

    def on_pause(duration: int):
        send_pause(duration)
        logger.info(f"Taking a break for {duration}s")

    workflow.set_on_video_callback(on_video)
    workflow.set_on_like_callback(on_like)
    workflow.set_on_follow_callback(on_follow)
    workflow.set_on_stats_callback(on_stats)
    workflow.set_on_pause_callback(on_pause)


def _return_to_tiktok_home(manager) -> None:
    """Best-effort reset to the TikTok home feed before the next query."""
    try:
        logger.info("Returning to TikTok home for next query...")
        for _ in range(3):
            manager.device_manager.device.press("back")
            time.sleep(0.5)

        selectors = [
            '//android.widget.FrameLayout[@content-desc="Home"]',
            '//android.widget.FrameLayout[@content-desc="Accueil"]',
            '//*[@content-desc="Home" or @content-desc="Accueil" or @text="Home" or @text="Accueil"]',
        ]

        for selector in selectors:
            if manager.device_manager.device.xpath(selector).click_exists(timeout=2):
                time.sleep(1.5)
                logger.info("Back to TikTok home")
                return

        logger.warning("Could not confirm Home tab click; continuing anyway")
    except Exception as exc:
        logger.warning(f"Could not navigate to home: {exc}")


def run_search_workflow(config: Dict[str, Any]):
    """Run the TikTok Search/Hashtag workflow."""
    device_id = config.get("deviceId")
    workflow_type = str(config.get("workflowType") or "search").strip().lower()
    search_queries = _normalize_search_queries(config)

    if not device_id:
        send_error("No device ID provided")
        return False

    if not search_queries:
        send_error("No search query provided")
        return False

    logger.info(f"Starting TikTok Search workflow on device: {device_id}")
    logger.info(
        f"Search queries ({len(search_queries)}): "
        f"{', '.join(_format_query_label(query, workflow_type) for query in search_queries)}"
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
            display_query = _format_query_label(search_query, workflow_type)

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
            _setup_search_workflow_callbacks(
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
                _return_to_tiktok_home(manager)

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
