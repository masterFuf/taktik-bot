"""TikTok unfollow bridge workflow runner."""

from __future__ import annotations

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import logger, send_error, send_message, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup


def run_unfollow_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok Unfollow workflow."""
    from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.payload import (
        unfollow_config_from_payload,
    )

    device_id = config.get("deviceId")
    bot_username = config.get("botUsername")
    # The page and the scheduler send `delay_min` / `delay_max`; this runner read `minDelay` /
    # `maxDelay`, so every run paused 1 to 3 s whatever was set. One reader now, shared with the
    # Agent handler.
    wf_config = unfollow_config_from_payload(config)
    max_unfollows = wf_config.max_unfollows

    if not device_id:
        send_error("No device ID provided")
        return False

    logger.info(f"👋 Starting TikTok Unfollow workflow on device: {device_id}")
    if bot_username:
        logger.info(f"📊 Bot account: @{bot_username}")
    logger.info(f"🎯 Max unfollows: {max_unfollows}")
    send_status("starting", f"Initializing TikTok Unfollow workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow import (
            UnfollowWorkflow,
        )

        manager, _ = tiktok_startup(device_id, fetch_profile=True)
        logger.info(f"⏱️ Pause between unfollows: {wf_config.min_delay:g}-{wf_config.max_delay:g} s")

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
        logger.success(f"✅ Unfollow workflow completed: {stats.unfollowed} users unfollowed")
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
