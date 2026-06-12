"""IPC callback wiring for TikTok search/hashtag bridge workflow."""

from __future__ import annotations

from typing import Dict

from bridges.tiktok.runtime.ipc import logger, send_action, send_pause, send_stats, send_video_info
from taktik.core.social_media.tiktok.services.navigation.reset import (
    return_to_tiktok_home as return_device_to_tiktok_home,
)


def setup_search_workflow_callbacks(workflow, aggregate_stats: Dict[str, int], sent_pics: set):
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
            watch_time=video_info.get("watch_time"),
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


def return_to_tiktok_home(manager) -> None:
    """Best-effort reset to the TikTok home feed before the next query."""
    return_device_to_tiktok_home(manager.device_manager.device, logger=logger)


__all__ = ["setup_search_workflow_callbacks", "return_to_tiktok_home"]
