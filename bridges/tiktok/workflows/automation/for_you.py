#!/usr/bin/env python3
"""
TikTok For You Bridge - For You page workflow
"""

from typing import Dict, Any

from bridges.tiktok.runtime.ipc import logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.automation.runtime.ai import install_profile_ai_hooks
from bridges.tiktok.runtime.video_callbacks import (
    send_final_video_stats,
    setup_video_workflow_callbacks,
)
from bridges.tiktok.workflows.automation.runtime.for_you_config import build_for_you_config


def _bridge_log(level: str, message: str) -> None:
    """(level, message) -> loguru, the shape the AI hooks expect. Same helper as the Followers
    and Target bridges — copied rather than shared because three lines behind an import is a
    module nobody would open twice."""
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def run_for_you_workflow(config: Dict[str, Any]):
    """Run the TikTok For You workflow."""
    device_id = config.get('deviceId')
    if not device_id:
        send_error("No device ID provided")
        return False
    
    logger.info(f"🚀 Starting TikTok For You workflow on device: {device_id}")
    send_status("starting", f"Initializing TikTok For You workflow on {device_id}")
    
    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.for_you.workflow import (
            ForYouWorkflow, ForYouConfig
        )
        
        # Common startup: connect, restart, navigate home, fetch profile
        manager, _bot_username = tiktok_startup(device_id, fetch_profile=True)

        # The AI hooks were installed by the Followers and Target bridges only, so a feed run
        # asking for `smartComments` got a workflow that could comment and no AI to write with:
        # the hook never installed, `_pick_configured_comment` found no texts, and the run
        # reported zero comments without a word. Same call, same place, as the other two.
        install_profile_ai_hooks(config, log=_bridge_log)
        
        workflow_config = build_for_you_config(ForYouConfig, config)
        
        # Create workflow
        logger.info("🎯 Creating For You workflow...")
        send_status("running", "Starting For You workflow")
        
        workflow = ForYouWorkflow(manager.device_manager.device, workflow_config)
        set_workflow(workflow)
        
        # Wire up standard IPC callbacks
        setup_video_workflow_callbacks(workflow)
        
        # Run workflow
        logger.info("▶️ Running workflow...")
        stats = workflow.run()
        
        # Send final stats + completion status
        send_final_video_stats(stats, "For You workflow")
        
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
