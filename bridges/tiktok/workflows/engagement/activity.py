#!/usr/bin/env python3
"""TikTok activity / system notifications bridge runner (inbox v2 - Phase 4, lecture seule).

Scrape les sections Activité / Notifications système de l'inbox et émet un event
``activity_notification`` par section. Aucune action device (lecture seule).
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.engagement.runtime.dm_callbacks import wire_notifications_read_callbacks


def run_activity_workflow(config: Dict[str, Any]):
    """Run the TikTok activity/system notifications read workflow."""
    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    max_items = config.get("maxItems", 20)
    logger.info(f"🔔 Lecture activité / notifs système sur {device_id} (max {max_items})")
    send_status("running", "Reading activity / system notifications")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import (
            DMConfig,
            DMWorkflow,
        )

        manager, _ = tiktok_startup(device_id, fetch_profile=True)
        workflow = DMWorkflow(manager.device_manager.device, DMConfig())
        set_workflow(workflow)
        wire_notifications_read_callbacks(workflow)

        notifications = workflow.read_notifications(max_items=max_items)

        logger.success(f"✅ {len(notifications)} notification(s) lue(s)")
        send_status("completed", f"Read {len(notifications)} notifications")
        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Activity read error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
