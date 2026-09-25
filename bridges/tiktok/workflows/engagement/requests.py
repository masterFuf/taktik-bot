#!/usr/bin/env python3
"""TikTok message-requests bridge runner (inbox v2 - Phase 3).

Two modes, set by the config:
- scrape, the default: open the message-requests page, list the requests and emit one event per
  item, without acting.
- execute: apply the decisions `{username, action: 'accept'|'decline', message?}`, replying after
  an accept when a message is given. Emits one result per decision.

The run is `run_tiktok_inbox` (core, flow `dm_requests`), the launcher the Agent handler
`tiktok.automation.dm_requests` (and so the CLI) calls too. This bridge only checks the request and
injects the startup that prints on stdout, its IPC and the stop signal.
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import _ipc, logger, send_error, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup_provider


def run_message_requests_workflow(config: Dict[str, Any]):
    """Run the TikTok message-requests workflow (scrape or execute)."""
    from taktik.core.social_media.tiktok.actions.business.workflows.dm.inbox_payload import (
        EXECUTE,
        REQUESTS,
        inbox_mode_from_payload,
        request_decisions_from_payload,
    )

    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    if inbox_mode_from_payload(config) == EXECUTE and not request_decisions_from_payload(config):
        send_error("No decisions to process")
        return False

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.inbox_agent_handler import (
            run_tiktok_inbox,
        )

        run_tiktok_inbox(
            config,
            flow=REQUESTS,
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
        error_msg = f"Message requests error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
