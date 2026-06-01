#!/usr/bin/env python3
"""TikTok DM sending workflow bridge runner."""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import logger, send_dm_stats, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.engagement.runtime.dm_callbacks import wire_dm_send_callbacks


def run_dm_send_workflow(config: Dict[str, Any]):
    """Run the TikTok DM sending workflow."""
    device_id = config.get("deviceId")
    messages = config.get("messages", [])

    if not device_id:
        send_error("No device ID provided")
        return False

    if not messages:
        send_error("No messages to send")
        return False

    logger.info(f"ðŸ“¤ Starting TikTok DM sending workflow on device: {device_id}")
    send_status("starting", f"Sending {len(messages)} messages")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import (
            DMConfig,
            DMWorkflow,
        )

        manager, _ = tiktok_startup(device_id, fetch_profile=True)

        workflow_config = DMConfig(
            delay_between_conversations=config.get("delayBetweenMessages", 1.0),
            delay_after_send=config.get("delayAfterSend", 0.5),
        )

        workflow = DMWorkflow(manager.device_manager.device, workflow_config)
        set_workflow(workflow)
        wire_dm_send_callbacks(workflow)

        logger.info(f"â–¶ï¸ Sending {len(messages)} messages...")
        send_status("running", f"Sending {len(messages)} messages")

        results = workflow.send_bulk_messages(messages)
        sent_count = sum(1 for result in results if result["success"])

        stats = workflow.get_stats()
        send_dm_stats(stats.to_dict())

        logger.success(f"âœ… DM sending completed: {sent_count}/{len(messages)} sent")
        send_status("completed", f"Sent {sent_count}/{len(messages)} messages")

        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"DM send error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
