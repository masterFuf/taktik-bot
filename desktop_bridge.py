#!/usr/bin/env python3
"""
Desktop Bridge for TAKTIK Bot
This script allows the TAKTIK Desktop app to launch bot sessions programmatically.
It accepts a JSON configuration and runs the appropriate workflow.
"""

import sys
import os
import json
import signal
import logging
import math
from typing import Optional, Dict, Any
from loguru import logger

# Configure logging for desktop integration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Structured message output for desktop app
def send_message(msg_type: str, **kwargs):
    """Send a structured JSON message to the desktop app."""
    message = {"type": msg_type, **kwargs}
    print(json.dumps(message), flush=True)

def send_status(status: str, message: str = ""):
    """Send status update to desktop app."""
    send_message("status", status=status, message=message)

def send_progress(current: int, total: int, action: str = ""):
    """Send progress update to desktop app."""
    send_message("progress", current=current, total=total, action=action)

def send_stats(likes: int = 0, follows: int = 0, comments: int = 0, profiles: int = 0):
    """Send stats update to desktop app."""
    send_message("stats", likes=likes, follows=follows, comments=comments, profiles=profiles)

def send_error(error: str):
    """Send error to desktop app."""
    send_message("error", error=error)

def send_log(level: str, message: str):
    """Send log message to desktop app."""
    send_message("log", level=level, message=message)


class DesktopBridge:
    """Bridge between Desktop app and TAKTIK Bot."""
    
    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get('deviceId')
        self.workflow_type = config.get('workflowType')
        self.target = config.get('target')
        self.limits = config.get('limits', {})
        self.probabilities = config.get('probabilities', {})
        self.filters = config.get('filters', {})
        self.session_config = config.get('session', {})
        self.language = config.get('language', 'en')
        self.running = True
        # API credentials passed from desktop app
        self.api_key = config.get('apiKey')
        self.license_key = config.get('licenseKey')
        self.device_manager = None
        self.automation = None
        
        # Media capture service
        self.media_capture_enabled = config.get('mediaCaptureEnabled', True)
        self.media_capture_service = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signal."""
        send_status("stopping", "Received shutdown signal")
        self.running = False
    
    def validate_config(self) -> bool:
        """Validate the configuration."""
        if not self.device_id:
            send_error("Device ID is required")
            return False
        if not self.workflow_type:
            send_error("Workflow type is required")
            return False
        if not self.target:
            send_error("Target is required")
            return False
        return True
    
    def setup_license(self) -> bool:
        """Setup and verify license using API key from desktop app."""
        try:
            send_status("initializing", "Setting up API credentials...")
            
            # Check if API key was passed from desktop app
            if self.api_key:
                send_log("info", "Using API key from desktop app")
                
                # Set API key in environment (required by bot internals)
                os.environ['TAKTIK_API_KEY'] = self.api_key
                
                # Configure database service with the API key
                from taktik.core.database import configure_db_service
                configure_db_service(self.api_key)
                
                # Configure unified_license_manager with API key (use _api_key internal attribute)
                from taktik.core.license.unified_license_manager import unified_license_manager
                unified_license_manager._api_key = self.api_key
                # Also update the api_client to use the API key
                from taktik.core.database.api_client import TaktikAPIClient
                unified_license_manager.api_client = TaktikAPIClient(api_key=self.api_key)
                send_log("debug", f"unified_license_manager._api_key configured: {self.api_key[:20]}...")
                
                send_status("license_valid", "API credentials configured")
                return True
            
            # Fallback: Try to load from local config (for CLI compatibility)
            send_log("info", "No API key from desktop, trying local config...")
            from taktik.core.license import unified_license_manager
            
            config = unified_license_manager.load_config()
            if config and config.get('license_key'):
                license_key = config['license_key']
                
                # Verify and get API key
                is_valid, api_key, license_data = unified_license_manager.verify_and_setup_license(license_key)
                
                if is_valid and api_key:
                    self.api_key = api_key
                    os.environ['TAKTIK_API_KEY'] = api_key
                    
                    from taktik.core.database import configure_db_service
                    configure_db_service(api_key)
                    
                    send_status("license_valid", f"License verified for {license_data.get('user', 'Unknown') if license_data else 'Unknown'}")
                    return True
            
            send_error("No valid API key found. Please log in to the desktop app first.")
            return False
            
        except Exception as e:
            send_error(f"License setup failed: {str(e)}")
            logger.exception("License setup failed")
            return False
    
    def connect_device(self) -> bool:
        """Connect to the specified device."""
        try:
            from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
            
            send_status("connecting", f"Connecting to device {self.device_id}...")
            
            self.device_manager = DeviceManager()
            result = self.device_manager.connect(self.device_id)
            
            if not result:
                send_error(f"Failed to connect to device {self.device_id}")
                return False
            
            if not self.device_manager.device:
                send_error("Device initialization error - device is None")
                return False
            
            send_status("connected", f"Connected to {self.device_id}")
            return True
            
        except Exception as e:
            send_error(f"Failed to connect to device: {str(e)}")
            logger.exception("Device connection failed")
            return False
    
    def launch_instagram(self) -> bool:
        """Launch Instagram on the device."""
        try:
            from taktik.core.social_media.instagram.core.manager import InstagramManager
            
            send_status("launching", "Launching Instagram...")
            
            instagram = InstagramManager(self.device_id)
            
            if not instagram.is_installed():
                send_error("Instagram is not installed on this device")
                return False
            
            if not instagram.launch():
                send_error("Failed to launch Instagram")
                return False
            
            send_status("instagram_ready", "Instagram launched successfully")
            return True
            
        except Exception as e:
            send_error(f"Failed to launch Instagram: {str(e)}")
            logger.exception("Instagram launch failed")
            return False
    
    def build_workflow_config(self) -> dict:
        """Build the workflow configuration matching CLI format."""
        max_profiles = self.limits.get('maxProfiles', 20)
        max_likes_per_profile = self.limits.get('maxLikesPerProfile', 2)
        like_percentage = self.probabilities.get('like', 80)
        follow_percentage = self.probabilities.get('follow', 20)
        comment_percentage = self.probabilities.get('comment', 5)
        story_percentage = self.probabilities.get('watchStories', 15)
        story_like_percentage = self.probabilities.get('likeStories', 10)
        min_followers = self.filters.get('minFollowers', 50)
        max_followers = self.filters.get('maxFollowers', 50000)
        min_posts = self.filters.get('minPosts', 5)
        max_followings = self.filters.get('maxFollowing', 7500)
        session_duration = self.session_config.get('durationMinutes', 60)
        min_delay = self.session_config.get('minDelay', 5)
        max_delay = self.session_config.get('maxDelay', 15)
        
        # Parse multiple targets (comma-separated) into a list
        # e.g., "user1,user2,user3" -> ["user1", "user2", "user3"]
        target_list = [t.strip() for t in self.target.split(',') if t.strip()]
        # For single target compatibility, use the first one
        primary_target = target_list[0] if target_list else self.target
        
        # Determine interaction type and workflow_type for SessionManager
        if self.workflow_type == 'target_followers':
            interaction_type = 'followers'
            action_type = 'interact_with_followers'
            session_workflow_type = 'target_followers'  # Must match SessionManager check
        elif self.workflow_type == 'target_following':
            interaction_type = 'following'
            action_type = 'interact_with_followers'
            session_workflow_type = 'target_followers'
        elif self.workflow_type == 'hashtags':
            interaction_type = 'hashtag'
            action_type = 'hashtag'
            session_workflow_type = 'hashtag'
        elif self.workflow_type == 'post_url':
            interaction_type = 'post-likers'
            action_type = 'post_url'
            session_workflow_type = 'target_followers'
        else:
            interaction_type = 'followers'
            action_type = 'interact_with_followers'
            session_workflow_type = 'target_followers'
        
        # Build config matching CLI format
        workflow_config = {
            "filters": {
                "min_followers": min_followers,
                "max_followers": max_followers,
                "min_followings": 0,
                "max_followings": max_followings,
                "min_posts": min_posts,
                "privacy_relation": "public_and_private",
                "blacklist_words": []
            },
            "session_settings": {
                "workflow_type": session_workflow_type,  # Must match SessionManager check for skip limits
                "total_profiles_limit": max_profiles,
                "total_follows_limit": math.ceil(max_profiles * (follow_percentage / 100)) if follow_percentage > 0 else 0,
                "total_likes_limit": math.ceil(max_profiles * max_likes_per_profile * (like_percentage / 100)) if like_percentage > 0 else 0,
                "session_duration_minutes": session_duration,
                "delay_between_actions": {
                    "min": min_delay,
                    "max": max_delay
                },
                "randomize_actions": True,
                "enable_screenshots": True,
                "screenshot_path": "screenshots"
            },
            "actions": [
                {
                    "type": action_type,
                    # Use primary_target for single-target fields, target_list for multi-target
                    "target_username": primary_target if action_type == 'interact_with_followers' else None,
                    "target_usernames": target_list if action_type == 'interact_with_followers' else [],
                    "hashtag": self.target if action_type == 'hashtag' else None,
                    "post_url": self.target if action_type == 'post_url' else None,
                    "interaction_type": interaction_type,
                    "max_interactions": max_profiles,
                    "like_posts": True,
                    "max_likes_per_profile": max_likes_per_profile,
                    "probabilities": {
                        "like_percentage": like_percentage,
                        "follow_percentage": follow_percentage,
                        "comment_percentage": comment_percentage,
                        "story_percentage": story_percentage,
                        "story_like_percentage": story_like_percentage
                    },
                    "like_settings": {
                        "enabled": like_percentage > 0,
                        "like_carousels": True,
                        "like_reels": True,
                        "randomize_order": True,
                        "methods": ["button_click", "double_tap"],
                        "verify_like_success": True,
                        "max_attempts_per_post": 2,
                        "delay_between_attempts": 2
                    },
                    "follow_settings": {
                        "enabled": follow_percentage > 0,
                        "unfollow_after_days": 3,
                        "verify_follow_success": True
                    },
                    "story_settings": {
                        "enabled": story_percentage > 0,
                        "watch_duration_range": [3, 8]
                    },
                    "story_like_settings": {
                        "enabled": story_like_percentage > 0,
                        "max_stories_per_user": 3,
                        "like_probability": story_like_percentage / 100.0,
                        "verify_like_success": True
                    },
                    "scrolling": {
                        "enabled": True,
                        "max_scroll_attempts": 3,
                        "scroll_delay": 1.5
                    }
                }
            ]
        }
        
        return workflow_config
    
    def run_workflow(self) -> bool:
        """Run the configured workflow."""
        try:
            from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation
            
            workflow_config = self.build_workflow_config()
            
            # Parse targets for display
            targets_display = ', @'.join([t.strip() for t in self.target.split(',') if t.strip()])
            send_status("starting", f"Starting {self.workflow_type} workflow for @{targets_display}")
            send_log("info", f"Configuration: {json.dumps(workflow_config, indent=2)}")
            
            # Create automation instance (matching CLI usage)
            send_status("initializing", "Initializing automation...")
            self.automation = InstagramAutomation(self.device_manager)
            
            # Initialize license limits
            self.automation._initialize_license_limits(self.api_key)
            
            # Apply config
            self.automation.config = workflow_config
            send_log("info", "Dynamic config applied")
            
            # Run the workflow
            send_status("running", "Running workflow...")
            self.automation.run_workflow()
            
            # Get final stats
            stats = self.automation.stats
            send_stats(
                likes=stats.get('likes', 0),
                follows=stats.get('follows', 0),
                comments=stats.get('comments', 0),
                profiles=stats.get('interactions', 0)
            )
            
            send_status("completed", "Workflow completed successfully")
            return True
                
        except Exception as e:
            send_error(f"Workflow error: {str(e)}")
            logger.exception("Workflow error")
            return False
    
    def start_media_capture(self) -> bool:
        """Start the media capture service for intercepting Instagram images."""
        if not self.media_capture_enabled:
            send_log("info", "Media capture disabled in config")
            return True
        
        try:
            from taktik.core.media import MediaCaptureService
            
            send_status("initializing", "Starting media capture service...")
            
            # Create callback to forward media events to desktop
            def on_media_event(event_type: str, data: Dict[str, Any]):
                send_message(event_type, **data)
            
            self.media_capture_service = MediaCaptureService(
                device_id=self.device_id,
                proxy_port=8888,
                desktop_bridge_callback=on_media_event
            )
            
            # Set up callbacks for logging
            def on_profile(profile):
                send_log("info", f"📸 Captured profile: @{profile.username} ({profile.follower_count} followers)")
                send_message("profile_captured", 
                    username=profile.username,
                    full_name=profile.full_name,
                    profile_pic_url=profile.profile_pic_url,
                    profile_pic_url_hd=profile.profile_pic_url_hd,
                    follower_count=profile.follower_count,
                    following_count=profile.following_count,
                    media_count=profile.media_count,
                    is_private=profile.is_private,
                    is_verified=profile.is_verified,
                    biography=profile.biography
                )
            
            def on_media(media):
                send_log("debug", f"🖼️ Captured media: {media.media_id} ({media.like_count} likes)")
                send_message("media_captured",
                    media_id=media.media_id,
                    media_type=media.media_type,
                    image_url=media.image_url,
                    like_count=media.like_count,
                    comment_count=media.comment_count,
                    caption=media.caption[:100] if media.caption else "",
                    username=media.username
                )
            
            self.media_capture_service.on_profile_captured = on_profile
            self.media_capture_service.on_media_captured = on_media
            
            if not self.media_capture_service.start():
                send_log("warning", "Media capture service failed to start (continuing without it)")
                self.media_capture_service = None
                return True  # Non-blocking failure
            
            send_status("media_capture_ready", "Media capture service started")
            return True
            
        except ImportError as e:
            send_log("warning", f"Media capture not available: {e}")
            return True  # Non-blocking
        except Exception as e:
            send_log("warning", f"Media capture failed: {e}")
            return True  # Non-blocking
    
    def stop_media_capture(self):
        """Stop the media capture service."""
        if self.media_capture_service:
            try:
                stats = self.media_capture_service.get_stats()
                send_log("info", f"Media capture stats: {stats['profiles_captured']} profiles, {stats['media_captured']} media")
                self.media_capture_service.stop()
            except Exception as e:
                send_log("warning", f"Error stopping media capture: {e}")
            self.media_capture_service = None
    
    def run(self) -> int:
        """Main entry point."""
        send_status("starting", "TAKTIK Desktop Bridge starting...")
        # Parse targets for display
        target_list = [t.strip() for t in self.target.split(',') if t.strip()]
        targets_display = ', '.join(target_list)
        send_log("info", f"Config: device={self.device_id}, workflow={self.workflow_type}, targets=[{targets_display}] ({len(target_list)} target(s))")
        
        # Validate configuration
        if not self.validate_config():
            return 1
        
        # Setup license
        if not self.setup_license():
            return 2
        
        # Connect to device
        if not self.connect_device():
            return 3
        
        # Start media capture (non-blocking if fails)
        self.start_media_capture()
        
        # Launch Instagram
        if not self.launch_instagram():
            self.stop_media_capture()
            return 4
        
        # Run workflow
        try:
            if not self.run_workflow():
                self.stop_media_capture()
                return 5
        finally:
            # Always stop media capture
            self.stop_media_capture()
        
        send_status("finished", "Session completed")
        return 0


def main():
    """Main entry point."""
    try:
        config = None
        
        # Method 1: Config file path as argument
        if len(sys.argv) >= 2:
            arg = sys.argv[1]
            
            # Check if it's a file path
            if os.path.isfile(arg):
                with open(arg, 'r', encoding='utf-8-sig') as f:
                    config = json.load(f)
                send_log("debug", f"Loaded config from file: {arg}")
            else:
                # Try to parse as JSON directly
                try:
                    config = json.loads(arg)
                    send_log("debug", "Parsed config from argument")
                except json.JSONDecodeError:
                    pass
        
        # Method 2: Read from stdin if no valid config yet
        if config is None:
            send_log("debug", "Reading config from stdin...")
            stdin_data = sys.stdin.read()
            if stdin_data.strip():
                config = json.loads(stdin_data)
                send_log("debug", "Parsed config from stdin")
        
        if config is None:
            send_error("No configuration provided. Use: python desktop_bridge.py <config.json> or pipe JSON to stdin")
            sys.exit(1)
        
        # Create and run bridge
        bridge = DesktopBridge(config)
        exit_code = bridge.run()
        
        sys.exit(exit_code)
        
    except json.JSONDecodeError as e:
        send_error(f"Invalid JSON configuration: {str(e)}")
        sys.exit(1)
    except Exception as e:
        send_error(f"Bridge error: {str(e)}")
        logger.exception("Bridge error")
        sys.exit(1)


if __name__ == "__main__":
    main()
