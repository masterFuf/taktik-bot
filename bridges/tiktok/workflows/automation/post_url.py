#!/usr/bin/env python3
"""TikTok Post URL bridge — engage the people who commented on one video.

Instagram's equivalent engages a post's LIKERS. TikTok shows nowhere who liked a video, so the
readable audience of a post is its commenters, and that is who this runs against.

The run is `run_tiktok_post_url`, the launcher the Agent handler `tiktok.automation.post_url` (and
so the CLI) calls too; the link, the budgets and the settings are read by the core
(`post_url/payload.py`, `followers/payload.py`). This bridge only injects the startup that prints
on stdout, the AI hooks wired to stdout, the live callbacks and the final stats.

The stats event stays `followers_stats` and keeps the followers shape, because the workflow returns
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
from bridges.tiktok.workflows.automation.runtime.ai import install_run_ai_hooks
from bridges.tiktok.workflows.automation.runtime.workflow_callbacks import wire_single_pass_callbacks
from taktik.core.social_media.tiktok.actions.business.workflows.followers.agent_handler import (
    new_session_totals,
)


def _bridge_log(level: str, message: str) -> None:
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def _startup(device_id: str):
    def start():
        from taktik.core.social_media.tiktok.workflows.runtime.startup import TikTokStartup

        manager, bot_username = tiktok_startup(device_id, fetch_profile=True)
        return TikTokStartup(device=manager.device_manager.device, bot_username=bot_username)

    return start


def _ai_hooks(ai_config, language) -> None:
    install_run_ai_hooks(ai_config, language, log=_bridge_log)


def _bind_workflow(workflow, post_url: str) -> None:
    set_workflow(workflow)
    send_message("workflow_start", target=post_url, targets=[], current_target_index=0)
    # No `total_targets`: this run DISCOVERS its commenters as it reads them, so the budget is a
    # ceiling, not a count. Announcing it would read as "3 of 20" on a video that has three
    # commenters -- the shape of the budget that once arrived as a follower cap.
    wire_single_pass_callbacks(workflow, new_session_totals())
    send_status("running", "Opening the video and reading its comments")


def _send_final_stats(stats) -> None:
    stats_dict = stats.to_dict()
    send_message("followers_stats", stats=stats_dict)
    send_message(
        "status",
        status="completed",
        message=f"Visited {stats.profiles_visited} commenter(s) of this video",
        completion_reason=stats_dict.get("completion_reason", "completed"),
    )
    logger.success(f"Post URL workflow completed: {stats_dict}")


def run_post_url_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok Post URL workflow."""
    from taktik.core.social_media.tiktok.actions.business.workflows.post_url.payload import (
        post_url_from_payload,
    )

    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    post_url = post_url_from_payload(config)
    if not post_url:
        send_error("No post URL provided")
        logger.error("No post URL provided for the post-url workflow")
        return False

    logger.info(f"Starting TikTok Post URL workflow on device: {device_id}")
    logger.info(f"Post: {post_url}")
    send_status("starting", f"Initializing TikTok Post URL workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.post_url.agent_handler import (
            run_tiktok_post_url,
        )

        run_tiktok_post_url(
            config,
            tiktok_startup=_startup(device_id),
            tiktok_ai_hooks=_ai_hooks,
            workflow_hook=_bind_workflow,
            on_finished=_send_final_stats,
        )
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


__all__ = ["run_post_url_workflow"]
