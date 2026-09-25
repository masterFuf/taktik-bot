#!/usr/bin/env python3
"""TikTok Post URL bridge — engage the people who commented on one video.

Instagram's equivalent engages a post's LIKERS. TikTok shows nowhere who liked a video, so the
readable audience of a post is its commenters, and that is who this runs against.

Flat like the target-profiles runner: one link, one pass, one session, one stats payload. The
stats event stays `followers_stats` and keeps the followers shape, because the workflow returns
`FollowersStats` and Electron already reads it -- a second event here would mean a second reader
on the app side for the same numbers.
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
from bridges.tiktok.workflows.automation.runtime.ai import install_profile_ai_hooks
from bridges.tiktok.workflows.automation.runtime.workflow_callbacks import wire_single_pass_callbacks
from taktik.core.social_media.tiktok.actions.business.workflows.followers.agent_handler import (
    new_session_totals,
)
from taktik.core.social_media.tiktok.actions.business.workflows.followers.payload import (
    followers_config_for_target,
    followers_settings_from_payload,
    session_limits_from_payload,
)


def _bridge_log(level: str, message: str) -> None:
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def read_post_url(config: Dict[str, Any]) -> str:
    """The link to open, in whichever key the app sends it.

    Not falling back to `searchQuery` or to any target field: this workflow acts on exactly one
    video, and guessing which one from an unrelated key is the wrong-target failure it exists to
    avoid. No link means no run.
    """
    for key in ("postUrl", "videoUrl", "url", "postLink"):
        raw = str(config.get(key) or "").strip()
        if raw:
            return raw
    return ""


def read_profile_budget(config: Dict[str, Any], max_commenters: int) -> int:
    """How many commenters to VISIT, in whichever key carries the budget.

    The page sends it twice, as `maxProfiles` and as `maxVideos` (the name the live panel reads,
    and the name `profile_budget_from_payload` falls back to for the followers road). This
    runner read `maxProfiles` and `maxFollowers` only, so a payload carrying the budget as
    `maxVideos` alone ran with the commenter count instead. Same order as the followers road:
    the specific name first, the shared one after, the commenter budget last.
    """
    for key in ("maxProfiles", "maxFollowers", "maxVideos"):
        value = config.get(key)
        if value:
            return int(value)
    return max_commenters


def run_post_url_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok Post URL workflow."""
    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    post_url = read_post_url(config)
    if not post_url:
        send_error("No post URL provided")
        logger.error("No post URL provided for the post-url workflow")
        return False

    bot_username = config.get("botUsername")
    logger.info(f"Starting TikTok Post URL workflow on device: {device_id}")
    logger.info(f"Post: {post_url}")
    send_status("starting", f"Initializing TikTok Post URL workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.post_url import (
            PostUrlConfig,
            PostUrlWorkflow,
        )

        manager, fetched_bot_username = tiktok_startup(device_id, fetch_profile=True)
        effective_bot_username = fetched_bot_username or bot_username

        install_profile_ai_hooks(config, log=_bridge_log)

        # How many commenters to RESOLVE, and how many to VISIT, are two different budgets and the
        # operator sets them separately: resolving a handle costs a profile open (~13 s) whether or
        # not that person is then worth interacting with.
        max_commenters = int(config.get("maxCommenters") or 20)
        max_profiles = read_profile_budget(config, max_commenters)

        # The interaction settings are read like every profile-visiting run's.
        max_likes, max_follows = session_limits_from_payload(config)
        workflow_config = followers_config_for_target(
            followers_settings_from_payload(config),
            search_query="",  # no source account: the video IS the source
            max_followers=max_profiles,
            max_likes_per_session=max_likes,
            max_follows_per_session=max_follows,
            config_class=PostUrlConfig,
        )
        workflow_config.post_url = post_url
        workflow_config.max_commenters = max_commenters
        workflow_config.max_comment_scrolls = int(config.get("maxCommentScrolls") or 8)

        workflow = PostUrlWorkflow(
            manager.device_manager.device, workflow_config, device_id=device_id
        )
        set_workflow(workflow)

        send_message("workflow_start", target=post_url, targets=[], current_target_index=0)

        total_stats = new_session_totals()
        # No `total_targets`: this run DISCOVERS its commenters as it reads them, so `max_profiles`
        # is a ceiling, not a count. Announcing it would read as "3 of 20" on a video that has
        # three commenters -- the shape of the budget that once arrived as a follower cap.
        wire_single_pass_callbacks(workflow, total_stats)

        send_status("running", "Opening the video and reading its comments")

        stats = workflow.run(bot_username=effective_bot_username)
        stats_dict = stats.to_dict()

        send_message("followers_stats", stats=stats_dict)
        send_message(
            "status",
            status="completed",
            message=f"Visited {stats.profiles_visited} commenter(s) of this video",
            completion_reason=stats_dict.get("completion_reason", "completed"),
        )

        logger.success(f"Post URL workflow completed: {stats_dict}")
        return True

    except ImportError as exc:
        error_msg = f"Import error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as exc:
        error_msg = f"Post URL workflow error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
