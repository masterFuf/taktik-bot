#!/usr/bin/env python3
"""TikTok DM reading bridge runner.

The run is `run_tiktok_dm_read` (core), the launcher the Agent handler `tiktok.automation.dm_read`
(and so the CLI) calls too: start, read the inbox, record the conversations under the account read
on the phone. This bridge only checks the device and injects what is specific to the desktop: the
startup that prints on stdout, its IPC for the live events, the stop signal.
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import _ipc, logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup_provider


def run_dm_read_workflow(config: Dict[str, Any]):
    """Run the TikTok DM reading workflow."""
    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    logger.info(f"📥 Starting TikTok DM reading workflow on device: {device_id}")
    send_status("starting", f"Initializing TikTok DM workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.agent_handler import (
            run_tiktok_dm_read,
        )

        run_tiktok_dm_read(
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
        error_msg = f"DM workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
