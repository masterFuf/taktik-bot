#!/usr/bin/env python3
"""TikTok notifications bridge: new followers, activity, hellos, suggested accounts.

The pass is `run_tiktok_notifications` (core), the launcher the Agent handler
`tiktok.automation.notifications` (and so the CLI) calls too. This bridge only injects the startup
that prints on stdout and the IPC the pass reports through.
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import _ipc
from bridges.tiktok.runtime.startup import tiktok_startup


def _startup(device_id: str):
    def start():
        from taktik.core.social_media.tiktok.workflows.runtime.startup import TikTokStartup

        manager, bot_username = tiktok_startup(device_id, fetch_profile=True)
        return TikTokStartup(device=manager.device_manager.device, bot_username=bot_username)

    return start


def run_notifications_workflow(config: Dict[str, Any]) -> bool:
    """Run the notifications pass. True when every step it was asked for ran."""
    from taktik.core.social_media.tiktok.actions.business.workflows.notifications.agent_handler import (
        run_tiktok_notifications,
    )

    device_id = config.get("deviceId") or config.get("device_id") or ""
    result = run_tiktok_notifications(config, notifier=_ipc, tiktok_startup=_startup(device_id))
    return bool(result["success"])


__all__ = ["run_notifications_workflow"]
