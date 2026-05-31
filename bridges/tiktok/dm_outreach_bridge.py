#!/usr/bin/env python3
"""TikTok DM Outreach Bridge - Cold DM workflow for TikTok."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional

# Bootstrap sys.path so absolute imports work when run as standalone script.
_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.common.database import SentDMService
from bridges.tiktok.base import logger, send_error, send_message, send_status, set_workflow
from taktik.core.social_media.tiktok.actions.business.workflows.dm.outreach import (
    TikTokDMOutreachWorkflow,
)


class BridgeNotifier:
    """Forward core workflow events to the historical bridge stdout contract."""

    def send(self, event_type: str, **payload: Any) -> None:
        if event_type == "status":
            send_status(payload.get("status", ""), payload.get("message", ""))
        elif event_type == "progress":
            send_message(
                "progress",
                current=payload.get("current"),
                total=payload.get("total"),
                username=payload.get("username"),
            )
        elif event_type == "dm_result":
            send_message(
                "dm_result",
                username=payload.get("username"),
                success=payload.get("success", False),
                error=payload.get("error"),
            )
        elif event_type == "stats":
            send_message("stats", stats=payload.get("stats", {}))


def check_dm_already_sent(account_id: int, recipient_username: str, platform: str = "tiktok") -> bool:
    """Check if a DM was already sent to this recipient."""
    return SentDMService.check_already_sent(account_id, recipient_username, platform=platform)


def record_sent_dm(
    account_id: int,
    recipient_username: str,
    message: str,
    success: bool,
    error_message: Optional[str] = None,
    session_id: Optional[str] = None,
    platform: str = "tiktok",
) -> None:
    """Record a sent DM in the database."""
    SentDMService.record(
        account_id,
        recipient_username,
        message,
        success,
        error_message,
        session_id,
        platform=platform,
    )


def run_dm_outreach_workflow(config: Dict[str, Any]):
    """Run the TikTok DM outreach workflow."""
    device_id = config.get("device_id") or config.get("deviceId")

    if not device_id:
        send_error("No device ID provided")
        return False

    logger.info(f"Starting TikTok DM Outreach on device: {device_id}")
    send_status("starting", "Initializing DM Outreach workflow")

    workflow = TikTokDMOutreachWorkflow(
        device_id,
        notifier=BridgeNotifier(),
        duplicate_checker=check_dm_already_sent,
        sent_dm_recorder=record_sent_dm,
    )
    set_workflow(workflow)

    if not workflow.connect():
        send_error("Failed to connect to device")
        return False

    recipients = config.get("recipients", [])
    messages = config.get("messages", [])
    delay_min = config.get("delayMin", config.get("delay_min", 30))
    delay_max = config.get("delayMax", config.get("delay_max", 60))
    max_dms = config.get("maxDms", config.get("max_dms", 50))
    account_id = config.get("accountId", config.get("account_id", 1))
    session_id = config.get("sessionId", config.get("session_id", device_id))

    logger.info(f"Config: {len(recipients)} recipients, {len(messages)} messages, max {max_dms} DMs")

    result = workflow.run(recipients, messages, delay_min, delay_max, max_dms, account_id, session_id)
    send_status(
        "completed",
        f"Completed: {result.get('dms_success', 0)} sent, {result.get('dms_failed', 0)} failed",
    )

    return result.get("success", False)


def main():
    """Main entry point - reads config from stdin."""
    logger.info("TikTok DM Outreach Bridge started")

    try:
        config_line = sys.stdin.readline()
        if not config_line:
            send_error("No configuration received")
            sys.exit(1)

        config = json.loads(config_line)
        logger.info(f"Received config: {json.dumps(config, indent=2)[:500]}...")

        success = run_dm_outreach_workflow(config)
        if not success:
            sys.exit(1)
    except json.JSONDecodeError as exc:
        send_error(f"Invalid JSON config: {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"DM Outreach error: {exc}", exc_info=True)
        send_error(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
