#!/usr/bin/env python3
"""TikTok DM reading workflow bridge runner."""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import logger, send_dm_stats, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.engagement.runtime.dm_callbacks import wire_dm_read_callbacks


def run_dm_read_workflow(config: Dict[str, Any]):
    """Run the TikTok DM reading workflow."""
    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    logger.info(f"ðŸ“¥ Starting TikTok DM reading workflow on device: {device_id}")
    send_status("starting", f"Initializing TikTok DM workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import (
            DMConfig,
            DMWorkflow,
        )

        manager, _ = tiktok_startup(device_id, fetch_profile=True)

        workflow_config = DMConfig(
            max_conversations=config.get("maxConversations", 20),
            skip_notifications=config.get("skipNotifications", True),
            skip_groups=config.get("skipGroups", False),
            only_unread=config.get("onlyUnread", False),
            delay_between_conversations=config.get("delayBetweenConversations", 1.0),
        )

        logger.info("ðŸ“¥ Creating DM workflow...")
        send_status("running", "Reading DM conversations")

        workflow = DMWorkflow(manager.device_manager.device, workflow_config)
        set_workflow(workflow)
        wire_dm_read_callbacks(workflow)

        logger.info("â–¶ï¸ Reading conversations...")
        conversations = workflow.read_conversations()

        stats = workflow.get_stats()
        send_dm_stats(stats.to_dict())

        logger.success(f"âœ… DM reading completed: {len(conversations)} conversations")
        send_status("completed", f"Read {len(conversations)} conversations")

        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"DM workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
