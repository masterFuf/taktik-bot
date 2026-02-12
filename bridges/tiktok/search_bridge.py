#!/usr/bin/env python3
"""
TikTok Search Bridge - Search/Target workflow
"""

import sys
import time
from typing import Dict, Any

from .base import (
    logger, send_status, send_error, set_workflow, tiktok_startup,
    setup_video_workflow_callbacks, send_final_video_stats
)


def run_search_workflow(config: Dict[str, Any]):
    """Run the TikTok Search/Target workflow."""
    device_id = config.get('deviceId')
    search_query = config.get('searchQuery')
    
    if not device_id:
        send_error("No device ID provided")
        return False
    
    if not search_query:
        send_error("No search query provided")
        return False
    
    logger.info(f"🔍 Starting TikTok Search workflow on device: {device_id}")
    logger.info(f"🔍 Search query: {search_query}")
    send_status("starting", f"Initializing TikTok Search workflow on {device_id}")
    
    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.search.workflow import (
            SearchWorkflow, SearchConfig
        )
        
        # Common startup: connect, restart, navigate home (no profile fetch needed)
        manager, _bot_username = tiktok_startup(device_id, fetch_profile=False)
        
        # Create workflow config from frontend config
        workflow_config = SearchConfig(
            search_query=search_query,
            max_videos=config.get('maxVideos', 50),
            min_watch_time=config.get('minWatchTime', 2.0),
            max_watch_time=config.get('maxWatchTime', 8.0),
            like_probability=config.get('likeProbability', 30) / 100.0,
            follow_probability=config.get('followProbability', 10) / 100.0,
            favorite_probability=config.get('favoriteProbability', 5) / 100.0,
            min_likes=config.get('minLikes'),
            max_likes=config.get('maxLikes'),
            max_likes_per_session=config.get('maxLikesPerSession', 50),
            max_follows_per_session=config.get('maxFollowsPerSession', 20),
            skip_already_liked=config.get('skipAlreadyLiked', True),
            skip_ads=config.get('skipAds', True),
            pause_after_actions=config.get('pauseAfterActions', 10),
            pause_duration_min=config.get('pauseDurationMin', 30.0),
            pause_duration_max=config.get('pauseDurationMax', 60.0),
        )
        
        # Create workflow
        logger.info(f"🎯 Creating Search workflow for: {search_query}")
        send_status("running", f"Searching for: {search_query}")
        
        workflow = SearchWorkflow(manager.device_manager.device, workflow_config)
        set_workflow(workflow)
        
        # Wire up standard IPC callbacks
        setup_video_workflow_callbacks(workflow)
        
        # Run workflow
        logger.info("▶️ Running search workflow...")
        stats = workflow.run()
        
        # Send final stats + completion status
        send_final_video_stats(stats, "Search workflow")
        
        return True
        
    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Search workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
