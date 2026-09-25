"""TikTok cold-DM bridge runtime.

The run is `run_tiktok_dm_outreach` (core), the launcher the Agent handler
`tiktok.standalone.tiktok_dm_outreach` (and so the CLI) calls too: skip who the account already
wrote to, message the others, mark each attempt in `sent_dms`. This bridge rotates the IP when the
page asks for it and injects what is specific to the desktop: the stdout events, the AI cost on
stdout, the stop signal.
"""

from __future__ import annotations

from typing import Any, Dict

from bridges.common.device.network import enforce_pre_session_ip_rotation
from bridges.tiktok.runtime.ipc import _ipc, logger, send_error, send_message, send_status, set_workflow


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


def _message_generator(ai_prompt: str, api_key: str):
    """The core's AI message per recipient, its cost reported on stdout (`ai_spend`)."""
    from taktik.core.social_media.tiktok.actions.business.workflows.dm.outreach_message import (
        outreach_message_generator,
    )

    return outreach_message_generator(ai_prompt, api_key, ipc=_ipc)


def run_dm_outreach_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok DM outreach workflow. Raises what the launcher refuses."""
    from taktik.core.social_media.tiktok.actions.business.workflows.dm.agent_handler import (
        run_tiktok_dm_outreach,
    )

    device_id = config.get("device_id") or config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    logger.info(f"Starting TikTok DM Outreach on device: {device_id}")
    send_status("starting", "Initializing DM Outreach workflow")

    result = run_tiktok_dm_outreach(
        config,
        device_id=device_id,
        notifier=BridgeNotifier(),
        message_generator=_message_generator,
        workflow_hook=set_workflow,
    )
    return bool(result.get("success", False))


class TikTokDMOutreachBridge:
    """One `dm_outreach_bridge` process: the IP rotation the page asks for, then the run."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def run(self) -> int:
        logger.info("TikTok DM Outreach Bridge started")
        try:
            # The page offers "reset IP before the run".
            device_id = self.config.get("device_id") or self.config.get("deviceId") or ""
            if device_id and not enforce_pre_session_ip_rotation(
                self.config, device_id, ipc=_ipc, label="DM outreach"
            ):
                return 1
            return 0 if run_dm_outreach_workflow(self.config) else 1
        except Exception as exc:
            logger.error(f"DM Outreach error: {exc}", exc_info=True)
            send_error(str(exc))
            return 1


__all__ = ["BridgeNotifier", "TikTokDMOutreachBridge", "run_dm_outreach_workflow"]
