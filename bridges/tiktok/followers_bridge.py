#!/usr/bin/env python3
"""
TikTok Followers Bridge - Followers workflow
"""

import sys
import time
from typing import Dict, Any

from .base import (
    logger, send_status, send_message, send_action, 
    send_pause, send_error, set_workflow
)


def run_followers_workflow(config: Dict[str, Any]):
    """Run the TikTok Followers workflow."""
    device_id = config.get('deviceId')
    search_query = config.get('searchQuery')
    bot_username = config.get('botUsername')  # TikTok account username for database tracking
    
    if not device_id:
        send_error("No device ID provided")
        return False
    
    if not search_query:
        send_error("No search query provided")
        return False
    
    logger.info(f"👥 Starting TikTok Followers workflow on device: {device_id}")
    if bot_username:
        logger.info(f"📊 Bot account: @{bot_username}")
    logger.info(f"🔍 Target user: {search_query}")
    send_status("starting", f"Initializing TikTok Followers workflow on {device_id}")
    
    try:
        # Import TikTok modules
        from taktik.core.social_media.tiktok import TikTokManager
        from taktik.core.social_media.tiktok.actions.business.workflows.followers_workflow import (
            FollowersWorkflow, FollowersConfig
        )
        
        # Create TikTok manager
        logger.info("📱 Connecting to device...")
        send_status("connecting", "Connecting to device")
        
        manager = TikTokManager(device_id=device_id)
        
        # Restart TikTok app (force stop + launch) to ensure clean state
        logger.info("📱 Restarting TikTok (clean state)...")
        send_status("launching", "Restarting TikTok app")
        
        if not manager.restart():
            send_error("Failed to restart TikTok app")
            return False
        
        time.sleep(4)  # Wait for app to fully load
        
        # Fetch own profile info for database tracking
        fetched_bot_username = None
        try:
            from taktik.core.social_media.tiktok.actions.business.actions.profile_actions import ProfileActions
            
            logger.info("📊 Fetching own profile info...")
            send_status("fetching_profile", "Fetching your TikTok profile info")
            
            profile_actions = ProfileActions(manager.device_manager.device)
            profile_info = profile_actions.fetch_own_profile()
            
            if profile_info:
                fetched_bot_username = profile_info.username
                logger.info(f"✅ Bot account: @{fetched_bot_username} ({profile_info.display_name})")
                logger.info(f"   Followers: {profile_info.followers_count}, Following: {profile_info.following_count}")
                
                # Send profile info to frontend
                send_message("bot_profile", profile={
                    "username": profile_info.username,
                    "display_name": profile_info.display_name,
                    "followers_count": profile_info.followers_count,
                    "following_count": profile_info.following_count,
                    "likes_count": profile_info.likes_count
                })
            else:
                logger.warning("⚠️ Could not fetch own profile info, database tracking will be limited")
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch profile info: {e}")
        
        # Use fetched username if available, otherwise fall back to config
        effective_bot_username = fetched_bot_username or bot_username
        
        # Create workflow config from frontend config
        workflow_config = FollowersConfig(
            search_query=search_query,
            max_followers=config.get('maxFollowers', 20),
            posts_per_profile=config.get('postsPerProfile', 2),
            min_watch_time=config.get('minWatchTime', 5.0),
            max_watch_time=config.get('maxWatchTime', 15.0),
            like_probability=config.get('likeProbability', 70) / 100.0,
            favorite_probability=config.get('favoriteProbability', 30) / 100.0,
            follow_probability=config.get('followProbability', 50) / 100.0,
            max_likes_per_session=config.get('maxLikesPerSession', 50),
            max_follows_per_session=config.get('maxFollowsPerSession', 20),
            min_delay=config.get('minDelay', 1.0),
            max_delay=config.get('maxDelay', 3.0),
            pause_after_actions=config.get('pauseAfterActions', 10),
            pause_duration_min=config.get('pauseDurationMin', 30.0),
            pause_duration_max=config.get('pauseDurationMax', 60.0),
            include_friends=config.get('includeFriends', False),
        )
        
        # Create workflow
        logger.info(f"🎯 Creating Followers workflow for: {search_query}")
        send_status("running", f"Following followers of: {search_query}")
        
        workflow = FollowersWorkflow(manager.device_manager.device, workflow_config)
        set_workflow(workflow)
        
        # Send workflow start event with target
        send_message("workflow_start", target=search_query)
        
        # Set callbacks for real-time updates
        def on_action(action_info):
            send_action(action_info.get('action', 'unknown'), action_info.get('target', ''))
            logger.info(f"🎯 Action: {action_info.get('action')} on @{action_info.get('target', '')}")
        
        def on_stats(stats_dict):
            send_message("followers_stats", stats={
                "followers_seen": stats_dict.get('followers_seen', 0),
                "profiles_visited": stats_dict.get('profiles_visited', 0),
                "posts_watched": stats_dict.get('posts_watched', 0),
                "likes": stats_dict.get('likes', 0),
                "favorites": stats_dict.get('favorites', 0),
                "follows": stats_dict.get('follows', 0),
                "already_friends": stats_dict.get('already_friends', 0),
                "skipped": stats_dict.get('skipped', 0),
                "errors": stats_dict.get('errors', 0)
            })
        
        def on_pause(duration: int):
            send_pause(duration)
            logger.info(f"⏸️ Taking a break for {duration}s")
        
        workflow.set_on_action_callback(on_action)
        workflow.set_on_stats_callback(on_stats)
        workflow.set_on_pause_callback(on_pause)
        
        # Run workflow
        logger.info("▶️ Running followers workflow...")
        stats = workflow.run(bot_username=effective_bot_username)
        
        # Send final stats with completion reason
        completion_reason = getattr(stats, 'completion_reason', 'unknown')
        send_message("followers_stats", stats={
            "followers_seen": stats.followers_seen,
            "profiles_visited": stats.profiles_visited,
            "posts_watched": stats.posts_watched,
            "likes": stats.likes,
            "favorites": stats.favorites,
            "follows": stats.follows,
            "already_friends": stats.already_friends,
            "skipped": stats.skipped,
            "errors": stats.errors,
            "completion_reason": completion_reason
        })
        
        logger.success(f"✅ Followers workflow completed: {stats.to_dict()}")
        
        # Send completion status with reason
        send_message("status", status="completed", 
                     message=f"Visited {stats.profiles_visited} profiles, {stats.likes} likes, {stats.follows} follows",
                     completion_reason=completion_reason)
        
        return True
        
    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Followers workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
