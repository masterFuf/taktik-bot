#!/usr/bin/env python3
"""
TikTok DM Send Bridge - DM sending workflow
"""

import sys
import time
from typing import Dict, Any

from .base import (
    logger, send_status, send_dm_sent, send_dm_progress, 
    send_dm_stats, send_error, set_workflow, tiktok_startup
)


def run_dm_send_workflow(config: Dict[str, Any]):
    """Run the TikTok DM sending workflow."""
    device_id = config.get('deviceId')
    messages = config.get('messages', [])  # List of {conversation, message}
    
    if not device_id:
        send_error("No device ID provided")
        return False
    
    if not messages:
        send_error("No messages to send")
        return False
    
    logger.info(f"📤 Starting TikTok DM sending workflow on device: {device_id}")
    send_status("starting", f"Sending {len(messages)} messages")
    
    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm_workflow import (
            DMWorkflow, DMConfig
        )
        
        # Common startup: connect, restart, navigate home (no profile fetch)
        manager, _ = tiktok_startup(device_id, fetch_profile=False)
        
        # Create workflow
        workflow_config = DMConfig(
            delay_between_conversations=config.get('delayBetweenMessages', 1.0),
            delay_after_send=config.get('delayAfterSend', 0.5),
        )
        
        workflow = DMWorkflow(manager.device_manager.device, workflow_config)
        set_workflow(workflow)
        
        # Set callbacks
        def on_message_sent(result):
            send_dm_sent(
                conversation=result.get('conversation', ''),
                success=result.get('success', False),
                error=result.get('error')
            )
        
        def on_stats(stats_dict):
            send_dm_stats(stats_dict)
        
        def on_progress(current, total, name):
            send_dm_progress(current, total, name)
        
        workflow.set_on_message_sent_callback(on_message_sent)
        workflow.set_on_stats_callback(on_stats)
        workflow.set_on_progress_callback(on_progress)
        
        # Send messages
        logger.info(f"▶️ Sending {len(messages)} messages...")
        send_status("running", f"Sending {len(messages)} messages")
        
        results = workflow.send_bulk_messages(messages)
        
        # Count successes
        sent_count = sum(1 for r in results if r['success'])
        
        # Send final stats
        stats = workflow.get_stats()
        send_dm_stats(stats.to_dict())
        
        logger.success(f"✅ DM sending completed: {sent_count}/{len(messages)} sent")
        send_status("completed", f"Sent {sent_count}/{len(messages)} messages")
        
        return True
        
    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"DM send error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
