"""Video workflow callback wiring for TikTok bridge runners."""

from bridges.tiktok.runtime.ipc import logger, send_action, send_pause, send_stats, send_status, send_video_info


def setup_video_workflow_callbacks(workflow) -> None:
    """
    Wire up standard IPC callbacks for video-based workflows.

    Used by For You, Search and related feed workflows.
    """
    _sent_pics: set = set()

    def on_video(video_info):
        author = video_info.get("author", "unknown")

        author_pic = None
        if author and author not in _sent_pics:
            try:
                detector = getattr(workflow, "detection", None)
                if detector is None:
                    detector = getattr(workflow, "detector", None)
                if detector and hasattr(detector, "get_author_profile_pic"):
                    author_pic = detector.get_author_profile_pic()
                    if author_pic:
                        _sent_pics.add(author)
            except Exception as e:
                logger.debug(f"Could not capture profile pic for @{author}: {e}")

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
        logger.info(f"❤️ Liked video by @{video_info.get('author', 'unknown')}")

    def on_follow(video_info):
        send_action("follow", video_info.get("author", "unknown"))
        logger.info(f"👤 Followed @{video_info.get('author', 'unknown')}")

    def on_stats(stats_dict):
        send_stats(
            videos_watched=stats_dict.get("videos_watched", 0),
            videos_liked=stats_dict.get("videos_liked", 0),
            users_followed=stats_dict.get("users_followed", 0),
            videos_favorited=stats_dict.get("videos_favorited", 0),
            videos_skipped=stats_dict.get("videos_skipped", 0),
            errors=stats_dict.get("errors", 0),
        )

    def on_pause(duration: int):
        send_pause(duration)
        logger.info(f"⏸️ Taking a break for {duration}s")

    workflow.set_on_video_callback(on_video)
    workflow.set_on_like_callback(on_like)
    workflow.set_on_follow_callback(on_follow)
    workflow.set_on_stats_callback(on_stats)
    workflow.set_on_pause_callback(on_pause)


def send_final_video_stats(stats, workflow_name: str = "Workflow") -> None:
    """Send final stats and completion status for a video-based workflow."""
    send_stats(
        videos_watched=stats.videos_watched,
        videos_liked=stats.videos_liked,
        users_followed=stats.users_followed,
        videos_favorited=stats.videos_favorited,
        videos_skipped=stats.videos_skipped,
        errors=stats.errors,
    )
    logger.success(f"✅ {workflow_name} completed: {stats.to_dict()}")
    send_status(
        "completed",
        f"{workflow_name} completed: {stats.videos_watched} videos, {stats.videos_liked} likes, {stats.users_followed} follows",
    )
