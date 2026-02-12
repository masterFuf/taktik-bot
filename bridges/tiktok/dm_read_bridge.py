#!/usr/bin/env python3
"""
TikTok DM Read Bridge - DM reading workflow
"""

import sys
import time
from typing import Dict, Any

from .base import (
    logger, send_status, send_dm_conversation, send_dm_progress, 
    send_dm_stats, send_error, set_workflow, tiktok_startup
)


def run_dm_read_workflow(config: Dict[str, Any]):
    """Run the TikTok DM reading workflow."""
    device_id = config.get('deviceId')
    if not device_id:
        send_error("No device ID provided")
        return False
    
    logger.info(f"📥 Starting TikTok DM reading workflow on device: {device_id}")
    send_status("starting", f"Initializing TikTok DM workflow on {device_id}")
    
    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import (
            DMWorkflow, DMConfig
        )
        
        # Common startup: connect, restart, navigate home (no profile fetch)
        manager, _ = tiktok_startup(device_id, fetch_profile=False)
        
        # Create workflow config from frontend config
        workflow_config = DMConfig(
            max_conversations=config.get('maxConversations', 20),
            skip_notifications=config.get('skipNotifications', True),
            skip_groups=config.get('skipGroups', False),
            only_unread=config.get('onlyUnread', False),
            delay_between_conversations=config.get('delayBetweenConversations', 1.0),
        )
        
        # Create workflow
        logger.info("📥 Creating DM workflow...")
        send_status("running", "Reading DM conversations")
        
        workflow = DMWorkflow(manager.device_manager.device, workflow_config)
        set_workflow(workflow)
        
        # Set callbacks for real-time updates
        def on_conversation(conv_data):
            send_dm_conversation(conv_data)
            logger.info(f"📖 Read conversation: {conv_data.get('name', 'unknown')}")
        
        def on_stats(stats_dict):
            send_dm_stats(stats_dict)
        
        def on_progress(current, total, name):
            send_dm_progress(current, total, name)
        
        workflow.set_on_conversation_callback(on_conversation)
        workflow.set_on_stats_callback(on_stats)
        workflow.set_on_progress_callback(on_progress)
        
        # Run workflow
        logger.info("▶️ Reading conversations...")
        conversations = workflow.read_conversations()
        
        # Send final stats
        stats = workflow.get_stats()
        send_dm_stats(stats.to_dict())
        
        logger.success(f"✅ DM reading completed: {len(conversations)} conversations")
        send_status("completed", f"Read {len(conversations)} conversations")
        
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
