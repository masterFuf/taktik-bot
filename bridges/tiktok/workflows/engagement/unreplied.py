#!/usr/bin/env python3
"""TikTok unreplied-conversations bridge runner (inbox v2 - Phase 2).

SCRAPE mode only: open the messaging screen, list the conversations flagging the unanswered ones
(whose last message came from them) and emit one event per item. REPLYING to the selected
conversations reuses the send workflow.

The run is `run_tiktok_inbox` (core, flow `dm_unreplied`), the launcher the Agent handler
`tiktok.automation.dm_unreplied` (and so the CLI) calls too. This bridge only checks the device and
injects the startup that prints on stdout, its IPC and the stop signal.
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import _ipc, logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup_provider


def run_unreplied_workflow(config: Dict[str, Any]):
    """Run the TikTok unreplied-conversations scrape workflow."""
    from taktik.core.social_media.tiktok.actions.business.workflows.dm.inbox_payload import (
        UNREPLIED,
        max_items_from_payload,
    )

    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    logger.info(
        f"📨 Scrape conversations non-répondues sur {device_id} (max {max_items_from_payload(UNREPLIED, config)})"
    )
    send_status("running", "Reading conversations")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.inbox_agent_handler import (
            run_tiktok_inbox,
        )

        run_tiktok_inbox(
            config,
            flow=UNREPLIED,
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
        error_msg = f"Unreplied scrape error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
