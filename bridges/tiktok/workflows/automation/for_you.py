#!/usr/bin/env python3
"""
TikTok For You Bridge - For You page workflow

The run is `run_tiktok_for_you`, the launcher the Agent handler `tiktok.automation.for_you` (and
so the CLI) calls too. Called by name rather than through the registry so the app's config
contract test can follow the payload. This bridge only injects what is specific to the desktop:
the startup that prints on stdout, the AI hooks wired to stdout, the live callbacks, the final
stats.
"""

from typing import Dict, Any

from bridges.tiktok.runtime.ipc import logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.automation.runtime.ai import install_run_ai_hooks
from bridges.tiktok.runtime.video_callbacks import (
    send_final_video_stats,
    setup_video_workflow_callbacks,
)


def _bridge_log(level: str, message: str) -> None:
    """(level, message) -> loguru, the shape the AI hooks expect. Same helper as the Followers
    and Target bridges — copied rather than shared because three lines behind an import is a
    module nobody would open twice."""
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def _startup(device_id: str):
    def start():
        from taktik.core.social_media.tiktok.workflows.runtime.startup import TikTokStartup

        manager, bot_username = tiktok_startup(device_id, fetch_profile=True)
        return TikTokStartup(device=manager.device_manager.device, bot_username=bot_username)

    return start


def _ai_hooks(ai_config, language) -> None:
    install_run_ai_hooks(ai_config, language, log=_bridge_log)


def _bind_workflow(workflow) -> None:
    logger.info("🎯 Creating For You workflow...")
    send_status("running", "Starting For You workflow")
    set_workflow(workflow)
    setup_video_workflow_callbacks(workflow)
    logger.info("▶️ Running workflow...")


def run_for_you_workflow(config: Dict[str, Any]):
    """Run the TikTok For You workflow."""
    device_id = config.get('deviceId')
    if not device_id:
        send_error("No device ID provided")
        return False

    logger.info(f"🚀 Starting TikTok For You workflow on device: {device_id}")
    send_status("starting", f"Initializing TikTok For You workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.for_you.agent_handler import (
            run_tiktok_for_you,
        )

        run_tiktok_for_you(
            config,
            tiktok_startup=_startup(device_id),
            tiktok_ai_hooks=_ai_hooks,
            workflow_hook=_bind_workflow,
            on_finished=lambda stats: send_final_video_stats(stats, "For You workflow"),
        )
        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
