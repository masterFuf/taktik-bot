#!/usr/bin/env python3
"""TikTok new-followers bridge runner (inbox v2 - Phase 1).

Two modes, set by the config:
- scrape, the default: open the new-followers page, list the items and emit them without acting,
  so the front can display them and the user select. On top, an OPTIONAL AI welcome pass
  (`ai.enabled` and `ai.newFollowers.enabled`): qualify each follower, record them for the
  attribution, follow back and send the welcome DM the verdicts allow.
- follow_back: follow back the selected usernames and emit one result event per username.

The run is `run_tiktok_inbox` (core, flow `new_followers`), the launcher the Agent handler
`tiktok.automation.new_followers` (and so the CLI) calls too; the welcome pass is
`dm/welcome_pass.py`. This bridge only checks the request and injects what is specific to the
desktop: the startup that prints on stdout, its IPC, the stop signal, the AI verdicts printed on
stdout and the permission to send the welcome DM.

The desktop side does not read everything the pass prints yet:
`TikTokNewFollowersStdoutService.handleScrapeOutput` routes `new_follower`/`status`/`error` only,
so the `ai_relevance`, `follow_back_result` and `dm_result` lines are dropped by the front until it
is taught to read them.
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import _ipc, logger, send_error, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup_provider


def _bridge_log(level: str, message: str) -> None:
    """Core -> loguru adapter. stderr only: stdout carries the bridge's JSON contract."""
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def run_new_followers_workflow(config: Dict[str, Any]):
    """Run the TikTok new-followers workflow (scrape or follow-back)."""
    from taktik.core.social_media.tiktok.actions.business.workflows.dm.inbox_payload import (
        FOLLOW_BACK,
        follow_back_usernames_from_payload,
        inbox_mode_from_payload,
    )

    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    if inbox_mode_from_payload(config) == FOLLOW_BACK and not follow_back_usernames_from_payload(config):
        send_error("No usernames to follow back")
        return False

    try:
        from bridges.tiktok.engagement.runtime.dm_outreach import BridgeNotifier
        from bridges.tiktok.workflows.automation.runtime.ai import build_welcome_qualifier
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.inbox_agent_handler import (
            run_tiktok_inbox,
        )

        run_tiktok_inbox(
            config,
            flow="new_followers",
            notifier=_ipc,
            tiktok_startup=tiktok_startup_provider(device_id),
            workflow_hook=set_workflow,
            tiktok_welcome_qualifier=lambda ai_config, language: build_welcome_qualifier(
                ai_config, language, log=_bridge_log
            ),
            outreach_notifier=BridgeNotifier(),
            send_welcome_dms=True,
        )
        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"New followers error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


__all__ = ["run_new_followers_workflow"]
