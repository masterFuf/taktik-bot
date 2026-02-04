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
    """Run the TikTok Followers workflow.
    
    Supports multi-target mode: if 'targets' array is provided, will process
    each target sequentially, distributing the max_followers limit across targets.
    Falls back to single 'searchQuery' for backwards compatibility.
    """
    device_id = config.get('deviceId')
    search_query = config.get('searchQuery')
    targets = config.get('targets', [])  # Multi-target support
    target_accounts = config.get('targetAccounts', [])  # From TikTokTarget page
    bot_username = config.get('botUsername')  # TikTok account username for database tracking
    
    if not device_id:
        send_error("No device ID provided")
        return False
    
    # Build targets list - use 'targets' or 'targetAccounts' array if provided, otherwise fall back to single searchQuery
    if target_accounts and len(target_accounts) > 0:
        target_list = [t.strip().replace('@', '') for t in target_accounts if t.strip()]
    elif targets and len(targets) > 0:
        target_list = [t.strip().replace('@', '') for t in targets if t.strip()]
    elif search_query:
        target_list = [search_query.strip().replace('@', '')]
    else:
        send_error("No target provided")
        return False
    
    if len(target_list) == 0:
        send_error("No valid targets provided")
        return False
    
    logger.info(f"👥 Starting TikTok Followers workflow on device: {device_id}")
    if bot_username:
        logger.info(f"📊 Bot account: @{bot_username}")
    logger.info(f"🔍 Targets ({len(target_list)}): {', '.join(['@' + t for t in target_list])}")
    send_status("starting", f"Initializing TikTok Followers workflow on {device_id}")
    
    # Calculate profiles per target for equitable distribution
    # Support both 'maxFollowers' (from TikTokFollowers page) and 'maxVideos' (from TikTokTarget page)
    max_followers_total = config.get('maxFollowers') or config.get('maxVideos', 20)
    profiles_per_target = max(1, max_followers_total // len(target_list))
    # Give remaining profiles to first targets
    extra_profiles = max_followers_total % len(target_list)
    
    logger.info(f"📊 Distribution: {profiles_per_target} profiles per target (total: {max_followers_total})")
    
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
        
        # Ensure we're on the For You feed (TikTok may restore previous state)
        try:
            from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions
            nav_actions = NavigationActions(manager.device_manager.device)
            
            # Press back to close any keyboard/popup, then navigate to Home
            nav_actions._press_back()
            time.sleep(0.5)
            nav_actions.navigate_to_home()
            time.sleep(1)
            logger.info("✅ Navigated to For You feed")
        except Exception as e:
            logger.warning(f"Could not navigate to Home: {e}")
        
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
        
        # Aggregate stats across all targets
        total_stats = {
            'followers_seen': 0,
            'profiles_visited': 0,
            'posts_watched': 0,
            'likes': 0,
            'favorites': 0,
            'follows': 0,
            'already_friends': 0,
            'skipped': 0,
            'errors': 0
        }
        
        # Remaining session limits (shared across targets)
        remaining_likes = config.get('maxLikesPerSession', 50)
        remaining_follows = config.get('maxFollowsPerSession', 20)
        
        # Workflow instance (will be created for each target)
        workflow = None
        completion_reason = 'completed'
        
        # Process each target sequentially
        for target_idx, current_target in enumerate(target_list):
                
            # Calculate profiles for this target
            target_max_followers = profiles_per_target + (1 if target_idx < extra_profiles else 0)
            
            # Skip if we've hit session limits
            if remaining_likes <= 0 and remaining_follows <= 0:
                logger.info(f"⏹️ Session limits reached, skipping remaining targets")
                break
            
            logger.info(f"\n{'='*50}")
            logger.info(f"🎯 Target {target_idx + 1}/{len(target_list)}: @{current_target}")
            logger.info(f"📊 Max profiles for this target: {target_max_followers}")
            logger.info(f"{'='*50}")
            
            # Send target switch event to frontend
            send_message("target_switch", 
                        current_target=current_target,
                        target_index=target_idx,
                        total_targets=len(target_list),
                        next_target=target_list[target_idx + 1] if target_idx + 1 < len(target_list) else None)
            
            # Create workflow config for this target
            workflow_config = FollowersConfig(
                search_query=current_target,
                max_followers=target_max_followers,
                posts_per_profile=config.get('postsPerProfile', 2),
                min_watch_time=config.get('minWatchTime', 5.0),
                max_watch_time=config.get('maxWatchTime', 15.0),
                like_probability=config.get('likeProbability', 70) / 100.0,
                favorite_probability=config.get('favoriteProbability', 30) / 100.0,
                follow_probability=config.get('followProbability', 50) / 100.0,
                story_like_probability=config.get('storyLikeProbability', 50) / 100.0,
                max_likes_per_session=remaining_likes,
                max_follows_per_session=remaining_follows,
                min_delay=config.get('minDelay', 1.0),
                max_delay=config.get('maxDelay', 3.0),
                pause_after_actions=config.get('pauseAfterActions', 10),
                pause_duration_min=config.get('pauseDurationMin', 30.0),
                pause_duration_max=config.get('pauseDurationMax', 60.0),
                include_friends=config.get('includeFriends', False),
            )
            
            # Create workflow for this target
            send_status("running", f"Processing target {target_idx + 1}/{len(target_list)}: @{current_target}")
            
            workflow = FollowersWorkflow(manager.device_manager.device, workflow_config)
            set_workflow(workflow)
            
            # Send workflow start event with target info
            send_message("workflow_start", 
                        target=current_target,
                        targets=target_list,
                        current_target_index=target_idx)
            
            # Set callbacks for real-time updates
            def on_action(action_info):
                send_action(action_info.get('action', 'unknown'), action_info.get('target', ''))
                logger.info(f"🎯 Action: {action_info.get('action')} on @{action_info.get('target', '')}")
            
            def on_stats(stats_dict):
                # Merge with total stats for display
                merged = {
                    "followers_seen": total_stats['followers_seen'] + stats_dict.get('followers_seen', 0),
                    "profiles_visited": total_stats['profiles_visited'] + stats_dict.get('profiles_visited', 0),
                    "posts_watched": total_stats['posts_watched'] + stats_dict.get('posts_watched', 0),
                    "likes": total_stats['likes'] + stats_dict.get('likes', 0),
                    "favorites": total_stats['favorites'] + stats_dict.get('favorites', 0),
                    "follows": total_stats['follows'] + stats_dict.get('follows', 0),
                    "already_friends": total_stats['already_friends'] + stats_dict.get('already_friends', 0),
                    "skipped": total_stats['skipped'] + stats_dict.get('skipped', 0),
                    "errors": total_stats['errors'] + stats_dict.get('errors', 0),
                    "current_target": current_target,
                    "target_index": target_idx,
                    "total_targets": len(target_list)
                }
                send_message("followers_stats", stats=merged)
            
            def on_pause(duration: int):
                send_pause(duration)
                logger.info(f"⏸️ Taking a break for {duration}s")
            
            workflow.set_on_action_callback(on_action)
            workflow.set_on_stats_callback(on_stats)
            workflow.set_on_pause_callback(on_pause)
            
            # Run workflow for this target
            logger.info(f"▶️ Running followers workflow for @{current_target}...")
            stats = workflow.run(bot_username=effective_bot_username)
            
            # Aggregate stats
            total_stats['followers_seen'] += stats.followers_seen
            total_stats['profiles_visited'] += stats.profiles_visited
            total_stats['posts_watched'] += stats.posts_watched
            total_stats['likes'] += stats.likes
            total_stats['favorites'] += stats.favorites
            total_stats['follows'] += stats.follows
            total_stats['already_friends'] += stats.already_friends
            total_stats['skipped'] += stats.skipped
            total_stats['errors'] += stats.errors
            
            # Update remaining limits
            remaining_likes -= stats.likes
            remaining_follows -= stats.follows
            
            logger.info(f"✅ Target @{current_target} completed: {stats.profiles_visited} profiles, {stats.likes} likes")
            
            # Check if we should continue to next target
            completion_reason = getattr(stats, 'completion_reason', 'unknown')
            if completion_reason in ['max_likes_reached', 'max_follows_reached', 'stopped_by_user']:
                logger.info(f"⏹️ Stopping multi-target workflow: {completion_reason}")
                break
            
            # If navigation failed, stop the workflow - don't try next target
            if completion_reason in ['navigation_failed', 'ERROR']:
                logger.warning(f"⚠️ Target @{current_target} failed with error ({completion_reason}), stopping workflow")
                break
            
            # Prepare for next target: go back to TikTok home
            if target_idx < len(target_list) - 1:
                logger.info(f"⏳ Switching to next target in 3 seconds...")
                time.sleep(2)
                
                # Navigate back to TikTok home before next target
                try:
                    logger.info("🏠 Returning to TikTok home for next target...")
                    # Press back multiple times to ensure we're at home
                    for _ in range(3):
                        manager.device_manager.device.press("back")
                        time.sleep(0.5)
                    
                    # Click on Home tab to ensure we're on the For You page
                    home_clicked = manager.device_manager.device.xpath(
                        '//android.widget.FrameLayout[@content-desc="Home"]'
                    ).click_exists(timeout=2)
                    
                    if not home_clicked:
                        # Try alternative selector
                        manager.device_manager.device.xpath(
                            '//*[@content-desc="Home" or @text="Home"]'
                        ).click_exists(timeout=2)
                    
                    time.sleep(1.5)
                    logger.info("✅ Back to TikTok home")
                except Exception as nav_error:
                    logger.warning(f"⚠️ Could not navigate to home: {nav_error}, trying anyway...")
        
        # Send final aggregated stats
        total_stats['completion_reason'] = completion_reason if 'completion_reason' in dir() else 'completed'
        send_message("followers_stats", stats=total_stats)
        
        logger.success(f"✅ Multi-target workflow completed: {total_stats}")
        
        # Send completion status
        send_message("status", status="completed", 
                     message=f"Visited {total_stats['profiles_visited']} profiles across {len(target_list)} targets",
                     completion_reason=total_stats.get('completion_reason', 'completed'))
        
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
