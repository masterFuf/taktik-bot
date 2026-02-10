#!/usr/bin/env python3
"""
TikTok Unfollow Bridge - Unfollow workflow for TikTok
Runs as standalone script, reads config from stdin
"""

import sys
import json
from typing import Dict, Any

from bridges.tiktok.base import (
    logger, send_status, send_message,
    send_error, set_workflow, tiktok_startup
)


def run_unfollow_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok Unfollow workflow."""
    device_id = config.get('deviceId')
    # Support both camelCase and snake_case from frontend
    max_unfollows = config.get('maxUnfollows') or config.get('max_unfollows', 20)
    bot_username = config.get('botUsername')
    include_friends = not (config.get('skipFriends') or config.get('skip_friends', True))
    
    if not device_id:
        send_error("No device ID provided")
        return False
    
    logger.info(f"👋 Starting TikTok Unfollow workflow on device: {device_id}")
    if bot_username:
        logger.info(f"📊 Bot account: @{bot_username}")
    logger.info(f"🎯 Max unfollows: {max_unfollows}")
    send_status("starting", f"Initializing TikTok Unfollow workflow on {device_id}")
    
    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.unfollow_workflow import (
            UnfollowWorkflow, UnfollowConfig
        )
        
        # Common startup: connect, restart, navigate home
        manager, _ = tiktok_startup(device_id, fetch_profile=False)
        
        # Create workflow config
        wf_config = UnfollowConfig(
            max_unfollows=max_unfollows,
            include_friends=include_friends,
            min_delay=config.get('minDelay', 1.0),
            max_delay=config.get('maxDelay', 3.0),
        )
        
        workflow = UnfollowWorkflow(manager.device_manager.device, wf_config)
        set_workflow(workflow)
        
        # Wire IPC callbacks
        def on_unfollow(username, count):
            send_message("unfollow_event", event="unfollowed", username=username, count=count)
        
        def on_skip(username):
            send_message("unfollow_event", event="skipped", reason="friends", username=username)
        
        def on_stats(stats_dict):
            stats_dict["target"] = max_unfollows
            send_message("unfollow_stats", stats=stats_dict)
        
        workflow.set_on_unfollow_callback(on_unfollow)
        workflow.set_on_skip_callback(on_skip)
        workflow.set_on_stats_callback(on_stats)
        
        # Run
        send_status("running", f"Unfollowing users (0/{max_unfollows})")
        stats = workflow.run()
        
        # Final stats + completion
        send_message("unfollow_stats", stats={"unfollowed": stats.unfollowed, "target": max_unfollows})
        logger.success(f"✅ Unfollow workflow completed: {stats.unfollowed} users unfollowed")
        send_status("completed", f"Unfollowed {stats.unfollowed} users")
        
        return True
        
    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Unfollow workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


def main():
    """Main entry point - read config from stdin and run workflow."""
    logger.info("🎵 TikTok Unfollow Bridge starting...")
    
    try:
        # Read config from stdin
        config_line = sys.stdin.readline()
        if not config_line:
            send_error("No config received from stdin")
            logger.error("No config received from stdin")
            sys.exit(1)
        
        config_data = json.loads(config_line)
        device_id = config_data.get('device_id')
        config = config_data.get('config', {})
        
        # Merge device_id into config
        config['deviceId'] = device_id
        
        logger.info(f"📋 Config received: device={device_id}, maxUnfollows={config.get('maxUnfollows', 20)}")
        
        # Run workflow
        success = run_unfollow_workflow(config)
        
        if success:
            logger.success("✅ TikTok Unfollow workflow completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ TikTok Unfollow workflow failed")
            sys.exit(1)
            
    except json.JSONDecodeError as e:
        send_error(f"Invalid JSON config: {e}")
        logger.error(f"JSON decode error: {e}")
        sys.exit(1)
    except Exception as e:
        send_error(f"Startup error: {e}")
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()