#!/usr/bin/env python3
"""
TikTok Followers Bridge - Followers workflow

The run is `run_tiktok_followers`, the launcher the Agent handler `tiktok.automation.followers`
(and so the CLI) calls too: targets in order, the profile budget shared between them, the like
and follow budgets carried over, the return home between two targets. Called by name rather than
through the registry so the app's config contract test can follow the payload. This bridge only
injects what is specific to the desktop: the startup that prints on stdout, the AI hooks wired to
stdout, the per-target events and live callbacks, the final stats.
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.automation.runtime.ai import install_run_ai_hooks
from bridges.tiktok.workflows.automation.runtime.followers_events import (
    send_final_followers_stats,
    send_followers_workflow_start,
    send_target_switch,
)
from bridges.tiktok.workflows.automation.runtime.followers_stats import wire_followers_callbacks


def _bridge_log(level: str, message: str) -> None:
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def _startup(device_id: str):
    def start():
        from taktik.core.social_media.tiktok.workflows.runtime.startup import TikTokStartup

        manager, bot_username = tiktok_startup(device_id, fetch_profile=True)
        return TikTokStartup(device=manager.device_manager.device, bot_username=bot_username)

    return start


def _ai_hooks(ai_config, language) -> None:
    install_run_ai_hooks(ai_config, language, log=_bridge_log)


def _bind_target(workflow, target) -> None:
    """Per target: announce it, then wire the live callbacks on top of the session's totals."""
    send_target_switch(target.target, target.index, target.targets)
    send_status("running", f"Processing target {target.index + 1}/{len(target.targets)}: @{target.target}")
    set_workflow(workflow)
    send_followers_workflow_start(target.target, target.targets, target.index)
    wire_followers_callbacks(workflow, target.totals, target.target, target.index, len(target.targets))


def run_followers_workflow(config: Dict[str, Any]):
    """Run the TikTok Followers workflow over every target of the payload."""
    from taktik.core.social_media.tiktok.actions.business.workflows.followers.payload import (
        followers_targets_from_payload,
        names_a_target_list,
    )

    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    target_list = followers_targets_from_payload(config)
    if not target_list:
        send_error("No valid targets provided" if names_a_target_list(config) else "No target provided")
        return False

    logger.info(f"Starting TikTok Followers workflow on device: {device_id}")
    logger.info(f"Targets ({len(target_list)}): {', '.join(['@' + target for target in target_list])}")
    send_status("starting", f"Initializing TikTok Followers workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.followers.agent_handler import (
            run_tiktok_followers,
        )

        run_tiktok_followers(
            config,
            tiktok_startup=_startup(device_id),
            tiktok_ai_hooks=_ai_hooks,
            target_hook=_bind_target,
            on_finished=lambda totals, targets: send_final_followers_stats(totals, len(targets)),
        )
        return True

    except ImportError as exc:
        error_msg = f"Import error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as exc:
        error_msg = f"Followers workflow error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
