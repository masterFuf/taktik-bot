#!/usr/bin/env python3
"""
TikTok For You Bridge - For You page workflow
"""

from typing import Dict, Any

from bridges.tiktok.runtime.ipc import logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.runtime.video_callbacks import (
    send_final_video_stats,
    setup_video_workflow_callbacks,
)
from bridges.tiktok.workflows.automation.runtime.for_you_config import build_for_you_config


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
