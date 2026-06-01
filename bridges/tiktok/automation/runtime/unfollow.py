"""TikTok unfollow bridge workflow runner."""

from __future__ import annotations

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import logger, send_error, send_message, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup


def run_unfollow_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok Unfollow workflow."""
    device_id = config.get("deviceId")
    max_unfollows = config.get("maxUnfollows") or config.get("max_unfollows", 20)
    bot_username = config.get("botUsername")
    include_friends = not (config.get("skipFriends") or config.get("skip_friends", True))

    if not device_id:
        send_error("No device ID provided")
        return False

    logger.info(f"ðŸ‘‹ Starting TikTok Unfollow workflow on device: {device_id}")
    if bot_username:
        logger.info(f"ðŸ“Š Bot account: @{bot_username}")
    logger.info(f"ðŸŽ¯ Max unfollows: {max_unfollows}")
    send_status("starting", f"Initializing TikTok Unfollow workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow import (
            UnfollowConfig,
            UnfollowWorkflow,
        )

        manager, _ = tiktok_startup(device_id, fetch_profile=True)

        wf_config = UnfollowConfig(
            max_unfollows=max_unfollows,
            include_friends=include_friends,
            min_delay=config.get("minDelay", 1.0),
            max_delay=config.get("maxDelay", 3.0),
        )

        workflow = UnfollowWorkflow(manager.device_manager.device, wf_config)
        set_workflow(workflow)

        def on_unfollow(username, count):
            send_message("unfollow_event", event="unfollowed", username=username, count=count)

        def on_skip(username):
            send_message("unfollow_event", event="skipped", reason="friends", username=username)

        def on_stats(stats_dict):
            stats_dict["target"] = max_unfollows
            send_message("unfollow_stats", stats=stats_dict)

        workflow.set_on_unfollow_callback(on_unfollow)
        workflow.set_on_skip_callback(on_skip)
        workflow.set_on_stats_callback(on_stats)

        send_status("running", f"Unfollowing users (0/{max_unfollows})")
        stats = workflow.run()

        send_message("unfollow_stats", stats={"unfollowed": stats.unfollowed, "target": max_unfollows})
        logger.success(f"âœ… Unfollow workflow completed: {stats.unfollowed} users unfollowed")
        send_status("completed", f"Unfollowed {stats.unfollowed} users")

        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Unfollow workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


__all__ = ["run_unfollow_workflow"]
