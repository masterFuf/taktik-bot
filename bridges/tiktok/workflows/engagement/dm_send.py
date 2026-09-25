#!/usr/bin/env python3
"""TikTok DM sending bridge runner.

The run is `run_tiktok_dm_send` (core), the launcher the Agent handler `tiktok.automation.dm_send`
(and so the CLI) calls too: start, send each message, record the ones that left under the account
read on the phone. This bridge only checks the device and the messages and injects what is
specific to the desktop: the startup that prints on stdout, its IPC for the live events, the stop
signal.
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import _ipc, logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup_provider


def run_dm_send_workflow(config: Dict[str, Any]):
    """Run the TikTok DM sending workflow."""
    from taktik.core.social_media.tiktok.actions.business.workflows.dm.payload import (
        dm_messages_from_payload,
    )

    device_id = config.get("deviceId")
    messages = dm_messages_from_payload(config)

    if not device_id:
        send_error("No device ID provided")
        return False

    if not messages:
        send_error("No messages to send")
        return False

    logger.info(f"📤 Starting TikTok DM sending workflow on device: {device_id}")
    send_status("starting", f"Sending {len(messages)} messages")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.agent_handler import (
            run_tiktok_dm_send,
        )

        run_tiktok_dm_send(
            config,
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
        error_msg = f"DM send error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
