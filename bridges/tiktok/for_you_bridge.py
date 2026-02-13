#!/usr/bin/env python3
"""
TikTok For You Bridge - For You page workflow
"""

import sys
import time
from typing import Dict, Any

from .base import (
    logger, send_status, send_error, set_workflow, tiktok_startup,
    setup_video_workflow_callbacks, send_final_video_stats
)


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
        
        # Create workflow config from frontend config
        workflow_config = ForYouConfig(
            max_videos=config.get('maxVideos', 50),
            min_watch_time=config.get('minWatchTime', 2.0),
            max_watch_time=config.get('maxWatchTime', 8.0),
            like_probability=config.get('likeProbability', 30) / 100.0,
            follow_probability=config.get('followProbability', 10) / 100.0,
            favorite_probability=config.get('favoriteProbability', 5) / 100.0,
            required_hashtags=config.get('requiredHashtags', []),
            excluded_hashtags=config.get('excludedHashtags', []),
            min_likes=config.get('minLikes'),
            max_likes=config.get('maxLikes'),
            max_likes_per_session=config.get('maxLikesPerSession', 50),
            max_follows_per_session=config.get('maxFollowsPerSession', 20),
            skip_already_liked=config.get('skipAlreadyLiked', True),
            skip_ads=config.get('skipAds', True),
            follow_back_suggestions=config.get('followBackSuggestions', False),
            pause_after_actions=config.get('pauseAfterActions', 10),
            pause_duration_min=config.get('pauseDurationMin', 30.0),
            pause_duration_max=config.get('pauseDurationMax', 60.0),
        )
        
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
