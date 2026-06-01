#!/usr/bin/env python3
"""
TikTok Followers Bridge - Followers workflow
"""

import time
from typing import Dict, Any

from bridges.tiktok.runtime.ipc import (
    logger, send_status, send_error, set_workflow
)
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.automation.runtime.followers_events import (
    send_final_followers_stats,
    send_followers_workflow_start,
    send_target_switch,
)
from bridges.tiktok.workflows.automation.runtime.followers_planning import (
    build_followers_config,
    build_target_list,
    calculate_target_distribution,
    has_empty_target_candidates,
    max_profiles_for_target,
    should_stop_after_target,
)
from bridges.tiktok.workflows.automation.runtime.followers_stats import (
    create_total_stats,
    record_target_stats,
    wire_followers_callbacks,
)
from taktik.core.social_media.tiktok.services.navigation.reset import return_to_tiktok_home


def run_followers_workflow(config: Dict[str, Any]):
    """Run the TikTok Followers workflow.
    
    Supports multi-target mode: if 'targets' array is provided, will process
    each target sequentially, distributing the max_followers limit across targets.
    Falls back to single 'searchQuery' for backwards compatibility.
    """
    device_id = config.get('deviceId')
    bot_username = config.get('botUsername')  # TikTok account username for database tracking
    
    if not device_id:
        send_error("No device ID provided")
        return False
    
    target_list = build_target_list(config)
    if not target_list:
        if has_empty_target_candidates(config):
            send_error("No valid targets provided")
        else:
            send_error("No target provided")
        return False
    
    logger.info(f"👥 Starting TikTok Followers workflow on device: {device_id}")
    if bot_username:
        logger.info(f"📊 Bot account: @{bot_username}")
    logger.info(f"🔍 Targets ({len(target_list)}): {', '.join(['@' + t for t in target_list])}")
    send_status("starting", f"Initializing TikTok Followers workflow on {device_id}")
    
    max_followers_total, profiles_per_target, extra_profiles = calculate_target_distribution(
        config,
        len(target_list),
    )
    
    logger.info(f"📊 Distribution: {profiles_per_target} profiles per target (total: {max_followers_total})")
    
    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.followers.workflow import (
            FollowersWorkflow, FollowersConfig
        )
        
        # Common startup: connect, restart, navigate home, fetch profile
        manager, fetched_bot_username = tiktok_startup(device_id, fetch_profile=True)
        
        # Use fetched username if available, otherwise fall back to config
        effective_bot_username = fetched_bot_username or bot_username
        
        total_stats = create_total_stats()
        
        # Remaining session limits (shared across targets)
        remaining_likes = config.get('maxLikesPerSession', 50)
        remaining_follows = config.get('maxFollowsPerSession', 20)
        
        completion_reason = 'completed'
        
        # Process each target sequentially
        for target_idx, current_target in enumerate(target_list):
                
            target_max_followers = max_profiles_for_target(
                target_idx,
                profiles_per_target,
                extra_profiles,
            )
            
            # Skip if we've hit session limits
            if remaining_likes <= 0 and remaining_follows <= 0:
                logger.info(f"⏹️ Session limits reached, skipping remaining targets")
                break
            
            logger.info(f"\n{'='*50}")
            logger.info(f"🎯 Target {target_idx + 1}/{len(target_list)}: @{current_target}")
            logger.info(f"📊 Max profiles for this target: {target_max_followers}")
            logger.info(f"{'='*50}")
            
            send_target_switch(current_target, target_idx, target_list)
            
            workflow_config = build_followers_config(
                FollowersConfig,
                config,
                current_target,
                target_max_followers,
                remaining_likes,
                remaining_follows,
            )
            
            # Create workflow for this target
            send_status("running", f"Processing target {target_idx + 1}/{len(target_list)}: @{current_target}")
            
            workflow = FollowersWorkflow(manager.device_manager.device, workflow_config)
            set_workflow(workflow)
            
            send_followers_workflow_start(current_target, target_list, target_idx)
            
            wire_followers_callbacks(
                workflow,
                total_stats,
                current_target,
                target_idx,
                len(target_list),
            )
            
            # Run workflow for this target
            logger.info(f"▶️ Running followers workflow for @{current_target}...")
            stats = workflow.run(bot_username=effective_bot_username)
            
            record_target_stats(total_stats, stats)
            
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
            if should_stop_after_target(completion_reason):
                logger.warning(f"⚠️ Target @{current_target} failed with error ({completion_reason}), stopping workflow")
                break
            
            # Prepare for next target: go back to TikTok home
            if target_idx < len(target_list) - 1:
                logger.info(f"⏳ Switching to next target in 3 seconds...")
                time.sleep(2)
                if not return_to_tiktok_home(manager.device_manager.device, logger=logger):
                    logger.warning("Could not navigate to home, trying next target anyway...")
        
        total_stats['completion_reason'] = completion_reason
        
        logger.success(f"✅ Multi-target workflow completed: {total_stats}")
        send_final_followers_stats(total_stats, len(target_list))
        
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
