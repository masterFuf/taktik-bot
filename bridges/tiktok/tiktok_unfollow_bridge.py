#!/usr/bin/env python3
"""
TikTok Unfollow Bridge - Unfollow workflow for TikTok
Runs as standalone script, reads config from stdin
"""

import sys
import os
import time
import json
from typing import Dict, Any

# Add parent directories to path for imports when run as standalone script
script_dir = os.path.dirname(os.path.abspath(__file__))
bridges_dir = os.path.dirname(script_dir)
bot_dir = os.path.dirname(bridges_dir)
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.tiktok.base import (
    logger, send_status, send_message, send_action,
    send_pause, send_error, set_workflow
)


def send_unfollow_event(username: str, success: bool, error: str = None):
    """Send unfollow event to frontend."""
    data = {
        "username": username,
        "success": success
    }
    if error:
        data["error"] = error
    send_message("unfollow", **data)


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
        # Import TikTok modules
        from taktik.core.social_media.tiktok import TikTokManager
        from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions
        from taktik.core.social_media.tiktok.actions.atomic.scroll_actions import ScrollActions
        from taktik.core.social_media.tiktok.actions.core.base_action import BaseAction
        
        # Create TikTok manager
        logger.info("📱 Connecting to device...")
        send_status("connecting", "Connecting to device")
        
        manager = TikTokManager(device_id=device_id)
        
        # Force stop then launch TikTok to ensure clean state
        logger.info("📱 Stopping TikTok...")
        send_status("launching", "Restarting TikTok app")
        manager.stop()  # Always stop first, even if not running
        time.sleep(2)
        
        logger.info("📱 Launching TikTok...")
        if not manager.launch():
            send_error("Failed to launch TikTok app")
            return False
        
        time.sleep(6)  # Wait for app to fully load (TikTok is slow)
        
        # Get device reference after restart (device is connected during restart)
        device = manager.device_manager.device
        if device is None:
            send_error("Device not connected")
            return False
        
        # Initialize action helpers
        nav_actions = NavigationActions(device)
        scroll_actions = ScrollActions(device)
        base_action = BaseAction(device)
        
        # Navigate to profile
        logger.info("👤 Navigating to profile...")
        send_status("navigating", "Going to profile")
        
        if not nav_actions.navigate_to_profile():
            send_error("Failed to navigate to profile")
            return False
        
        time.sleep(2)
        
        # Click on Following count to open following list
        logger.info("📋 Opening following list...")
        send_status("running", "Opening following list")
        
        following_selectors = [
            '//*[contains(@content-desc, "Following")]',
            '//*[contains(@text, "Following")]',
            '//android.widget.TextView[contains(@text, "Following")]',
        ]
        
        if not base_action._find_and_click(following_selectors, timeout=5):
            send_error("Failed to open following list")
            return False
        
        time.sleep(2)
        
        # Unfollow loop
        unfollowed_count = 0
        scroll_attempts = 0
        max_scroll_attempts = 10
        
        send_status("running", f"Unfollowing users (0/{max_unfollows})")
        
        while unfollowed_count < max_unfollows:
            # Find all Following/Friends buttons at once
            all_buttons_selector = '//*[@text="Following" or @text="Friends"][@clickable="true"]'
            elements = device.xpath(all_buttons_selector).all()
            
            if not elements:
                # No buttons found, try scrolling
                scroll_attempts += 1
                if scroll_attempts >= max_scroll_attempts:
                    logger.info("No more users to unfollow (no buttons found)")
                    break
                
                logger.info("No buttons found, scrolling...")
                scroll_actions.scroll_profile_videos(direction='down')
                time.sleep(1)
                continue
            
            logger.info(f"Found {len(elements)} buttons")
            
            # Track if we unfollowed anyone this iteration
            unfollowed_this_round = 0
            skipped_friends = 0
            
            for elem in elements:
                if unfollowed_count >= max_unfollows:
                    break
                
                try:
                    btn_text = elem.text or ''
                    
                    # Skip if it's a "Friends" button (mutual follow)
                    if 'Friends' in btn_text and not include_friends:
                        skipped_friends += 1
                        # Send skip event to frontend
                        send_message("unfollow_event", event="skipped", reason="friends")
                        continue
                    
                    # Click the button to unfollow
                    elem.click()
                    time.sleep(1)
                    
                    # Handle confirmation dialog if present
                    confirm_selectors = [
                        '//*[@text="Unfollow"][@clickable="true"]',
                        '//*[contains(@text, "Unfollow")][@clickable="true"]',
                    ]
                    base_action._find_and_click(confirm_selectors, timeout=2, human_delay=False)
                    
                    unfollowed_count += 1
                    unfollowed_this_round += 1
                    logger.info(f"✅ Unfollowed user ({unfollowed_count}/{max_unfollows})")
                    
                    # Send stats update to frontend
                    send_message("unfollow_stats", stats={
                        "unfollowed": unfollowed_count,
                        "skipped": skipped_friends,
                        "target": max_unfollows
                    })
                    
                    # Human-like delay
                    delay = config.get('minDelay', 1.0) + (config.get('maxDelay', 3.0) - config.get('minDelay', 1.0)) * 0.5
                    time.sleep(delay)
                    
                except Exception as e:
                    logger.warning(f"Failed to unfollow: {e}")
                    continue
            
            # If we only found Friends buttons and skipped them all, scroll
            if unfollowed_this_round == 0:
                if skipped_friends > 0:
                    logger.info(f"Skipped {skipped_friends} Friends buttons, scrolling...")
                scroll_attempts += 1
                if scroll_attempts >= max_scroll_attempts:
                    logger.info("No more users to unfollow (only Friends remaining)")
                    break
                
                scroll_actions.scroll_profile_videos(direction='down')
                time.sleep(1)
            else:
                # Reset scroll attempts if we made progress
                scroll_attempts = 0
        
        # Send final stats
        send_message("unfollow_stats", stats={
            "unfollowed": unfollowed_count,
            "target": max_unfollows
        })
        
        logger.success(f"✅ Unfollow workflow completed: {unfollowed_count} users unfollowed")
        send_status("completed", f"Unfollowed {unfollowed_count} users")
        
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