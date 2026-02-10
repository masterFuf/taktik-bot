#!/usr/bin/env python3
"""
TikTok For You Bridge - For You page workflow
"""

import sys
import time
from typing import Dict, Any

from .base import (
    logger, send_status, send_stats, send_video_info, send_action, 
    send_pause, send_error, set_workflow, tiktok_startup
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
        from taktik.core.social_media.tiktok.actions.business.workflows.for_you_workflow import (
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
        
        # Set callbacks for real-time updates
        def on_video(video_info):
            send_video_info(
                author=video_info.get('author', 'unknown'),
                description=video_info.get('description'),
                like_count=video_info.get('like_count'),
                is_liked=video_info.get('is_liked', False),
                is_followed=video_info.get('is_followed', False),
                is_ad=video_info.get('is_ad', False)
            )
        
        def on_like(video_info):
            send_action("like", video_info.get('author', 'unknown'))
            logger.info(f"❤️ Liked video by @{video_info.get('author', 'unknown')}")
        
        def on_follow(video_info):
            send_action("follow", video_info.get('author', 'unknown'))
            logger.info(f"👤 Followed @{video_info.get('author', 'unknown')}")
        
        def on_stats(stats_dict):
            send_stats(
                videos_watched=stats_dict.get('videos_watched', 0),
                videos_liked=stats_dict.get('videos_liked', 0),
                users_followed=stats_dict.get('users_followed', 0),
                videos_favorited=stats_dict.get('videos_favorited', 0),
                videos_skipped=stats_dict.get('videos_skipped', 0),
                errors=stats_dict.get('errors', 0)
            )
        
        def on_pause(duration: int):
            send_pause(duration)
            logger.info(f"⏸️ Taking a break for {duration}s")
        
        workflow.set_on_video_callback(on_video)
        workflow.set_on_like_callback(on_like)
        workflow.set_on_follow_callback(on_follow)
        workflow.set_on_stats_callback(on_stats)
        workflow.set_on_pause_callback(on_pause)
        
        # Run workflow
        logger.info("▶️ Running workflow...")
        stats = workflow.run()
        
        # Send final stats
        send_stats(
            videos_watched=stats.videos_watched,
            videos_liked=stats.videos_liked,
            users_followed=stats.users_followed,
            videos_favorited=stats.videos_favorited,
            videos_skipped=stats.videos_skipped,
            errors=stats.errors
        )
        
        logger.success(f"✅ Workflow completed: {stats.to_dict()}")
        send_status("completed", f"Workflow completed: {stats.videos_watched} videos, {stats.videos_liked} likes, {stats.users_followed} follows")
        
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
