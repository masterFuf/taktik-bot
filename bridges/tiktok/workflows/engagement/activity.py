#!/usr/bin/env python3
"""TikTok activity / system notifications bridge runner (inbox v2 - Phase 4, read-only).

Reads the activity and system-notification sections of the inbox and emits one event per
section. No device action.

The run is `run_tiktok_inbox` (core, flow `dm_activity`), the launcher the Agent handler
`tiktok.automation.dm_activity` (and so the CLI) calls too. This bridge only checks the device and
injects the startup that prints on stdout, its IPC and the stop signal.
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import _ipc, logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup_provider


def run_activity_workflow(config: Dict[str, Any]):
    """Run the TikTok activity/system notifications read workflow."""
    from taktik.core.social_media.tiktok.actions.business.workflows.dm.inbox_payload import (
        ACTIVITY,
        max_items_from_payload,
    )

    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    logger.info(
        f"🔔 Lecture activité / notifs système sur {device_id} (max {max_items_from_payload(ACTIVITY, config)})"
    )
    send_status("running", "Reading activity / system notifications")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.inbox_agent_handler import (
            run_tiktok_inbox,
        )

        run_tiktok_inbox(
            config,
            flow=ACTIVITY,
            notifier=_ipc,
            tiktok_startup=tiktok_startup_provider(device_id),
            workflow_hook=set_workflow,
        )
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
