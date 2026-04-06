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

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.connection import ConnectionService
from bridges.common.app_manager import AppService
from bridges.instagram.base import (
    logger, _ipc,
    send_message, send_status, send_progress, send_stats,
    send_instagram_stats, send_instagram_action, send_instagram_profile_visit,
    send_error, send_log,
    send_unfollow_event, send_follow_event, send_like_event,
    send_post_skipped, send_current_post,
    send_profile_captured,
    setup_stats_callback,
)

# Configure logging for desktop integration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class DebugBridge:
    """Bridge for debug commands (analyze, detect)."""
    
    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get('deviceId')
        self.mode = config.get('mode', 'analyze')  # analyze, detect
    
    def run(self) -> int:
        """Run debug command."""
        try:
            send_log("debug", f"Starting debug command: mode={self.mode}, device={self.device_id}")
            
            from taktik.core.device import DeviceManager
            send_log("debug", "DeviceManager imported successfully")
            
            if not self.device_id:
                send_error("Device ID is required")
                return 1
            
            send_log("debug", f"Connecting to device {self.device_id}...")
            device = DeviceManager.connect_to_device(self.device_id)
            if not device:
                send_error(f"Failed to connect to device {self.device_id}")
                return 2
            
            send_log("info", f"Connected to device {self.device_id}")
            
            if self.mode == 'analyze':
                return self._analyze(device)
            elif self.mode == 'detect':
                return self._detect(device)
            else:
                send_error(f"Unknown debug mode: {self.mode}")
                return 3
                
        except ImportError as e:
            send_error(f"Import error: {str(e)}")
            logger.exception("Import error in DebugBridge")
            return 1
        except Exception as e:
            import traceback
            send_error(f"Debug error: {str(e)}")
            send_log("error", f"Traceback: {traceback.format_exc()}")
            logger.exception("Debug error")
            return 1
    
    def _analyze(self, device) -> int:
        """Analyze current screen - capture screenshot and UI dump."""
        try:
            from taktik.utils.ui_dump import dump_ui_hierarchy, capture_screenshot
            import tempfile
            import os
            
            # Use temp directory for output
            output_dir = os.path.join(tempfile.gettempdir(), 'taktik_debug')
            os.makedirs(output_dir, exist_ok=True)
            send_log("debug", f"Output directory: {output_dir}")
            
            send_log("debug", "Capturing screenshot...")
            screenshot_path = capture_screenshot(device, output_dir)
            
            send_log("debug", "Dumping UI hierarchy...")
            dump_path = dump_ui_hierarchy(device, output_dir)
            
            result = {
                'success': True,
                'screenshotPath': screenshot_path,
                'dumpPath': dump_path
            }
            
            # Output result as JSON for the desktop app to parse
            if screenshot_path:
                send_log("info", f"Screenshot saved: {screenshot_path}")
            else:
                send_log("warning", "Screenshot capture failed")
                
            if dump_path:
                send_log("info", f"UI dump: {dump_path}")
            else:
                send_log("warning", "UI dump failed")
            
            send_message("debug_result", **result)
            return 0
            
        except Exception as e:
            import traceback
            send_error(f"Analyze error: {str(e)}")
            send_log("error", f"Traceback: {traceback.format_exc()}")
            return 1
    
    def _detect(self, device) -> int:
        """Detect and handle problematic pages (Instagram or TikTok)."""
        # Detect which app is in foreground
        try:
            current_app = device.app_current()
            package = current_app.get('package', '')
            send_log("info", f"Current app: {package}")
        except Exception as e:
            send_log("warning", f"Could not detect current app: {e}")
            package = ''
        
        # Use appropriate detector based on app
        if 'musically' in package or 'tiktok' in package.lower():
            # TikTok popup handling is done by popup_handler.py in workflows
            send_log("info", "TikTok detected — popup handling is managed by workflow popup_handler")
            detected = False
            handled = False
        else:
            # Default to Instagram
            send_log("info", "Using Instagram problematic page detector")
            from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
            detector = ProblematicPageDetector(device, debug_mode=True)
            result_data = detector.detect_and_handle_problematic_pages()
            # Instagram detector returns dict or bool
            if isinstance(result_data, dict):
                detected = result_data.get('detected', False)
                handled = result_data.get('closed', False)
            else:
                detected = bool(result_data)
                handled = detected
        
        result = {
            'success': True,
            'detected': detected,
            'handled': handled
        }
        
        if detected:
            send_log("info", "Problematic page detected and handled")
        else:
            send_log("info", "No problematic pages detected")
        
        send_message("debug_result", **result)
        return 0


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
        self.comments_config = config.get('comments', {})
        self.unfollow_config = config.get('unfollow', {})  # Unfollow specific settings
        self.language = config.get('language', 'en')
        self.package_name = config.get('packageName')  # Clone package (e.g. com.instagram.android.c1)
        self.running = True
        # Shared services
        self._connection = ConnectionService(self.device_id) if self.device_id else None
        self._app = None  # initialized after connect
        self.device_manager = None  # backward-compatible alias
        self.automation = None
        
        # AI mode configuration
        self.ai_config = config.get('ai', {})
        self.ai_enabled = self.ai_config.get('enabled', False)
        self.ai_service = None
        if self.ai_enabled:
            api_key = self.ai_config.get('openrouterApiKey', '')
            if api_key and len(api_key) > 5:
                from bridges.common.ai_service import AIService
                self.ai_service = AIService(api_key=api_key, ipc=_ipc)
                send_log("info", "🤖 AI mode enabled — Smart Comments / Profile Analysis / Post Analysis")
            else:
                send_log("warning", "AI mode requested but no OpenRouter API key provided")
                self.ai_enabled = False
        
        # Media capture service
        self.media_capture_enabled = config.get('mediaCaptureEnabled', False)
        self.media_capture_service = None
        
        # Setup signal handlers for graceful shutdown
        from bridges.common.signal_handler import setup_signal_handlers
        setup_signal_handlers(ipc=_ipc)
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
        """Setup database service for the bot process."""
        try:
            send_status("initializing", "Setting up database service...")
            
            # Configure local database service (SQLite)
            from taktik.core.database import configure_db_service
            configure_db_service()
            
            send_status("license_valid", "Database service configured")
            return True
            
        except Exception as e:
            send_error(f"Database setup failed: {str(e)}", error_code="LICENSE_SETUP_FAILED")
            logger.exception("Database setup failed")
            return False
    
    def connect_device(self) -> bool:
        """Connect to the specified device using ConnectionService."""
        try:
            send_status("connecting", f"Connecting to device {self.device_id}...")
            
            if not self._connection:
                self._connection = ConnectionService(self.device_id)
            
            if not self._connection.connect():
                send_error(f"Failed to connect to device {self.device_id}", error_code="DEVICE_CONNECTION_FAILED")
                return False
            
            # Backward-compatible alias
            self.device_manager = self._connection.device_manager
            self._app = AppService(self._connection, platform="instagram", package_override=self.package_name)
            
            send_status("connected", f"Connected to {self.device_id}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                send_error(f"Device connection timed out: {error_msg}", error_code="DEVICE_CONNECTION_TIMEOUT")
            else:
                send_error(f"Failed to connect to device: {error_msg}", error_code="DEVICE_CONNECTION_FAILED")
            logger.exception("Device connection failed")
            return False
    
    def launch_instagram(self) -> bool:
        """Launch Instagram on the device using ConnectionService + AppService."""
        try:
            send_status("launching", "Launching Instagram...")
            
            # Check ATX health via ConnectionService (non-blocking)
            atx_result = self._connection.check_atx_health(repair=True, max_retries=3)
            if not atx_result["atx_healthy"]:
                error_detail = atx_result.get("error", "Unknown")
                if atx_result.get("repaired"):
                    send_status("atx_repaired", "UIAutomator2 agent repaired successfully")
                else:
                    logger.warning(f"ATX repair failed: {error_detail} - continuing anyway")
                    send_log("warning", f"ATX repair failed ({error_detail}) but continuing - workflow may still work")
            
            # Check Instagram is installed
            if not self._app.is_installed():
                send_error("Instagram is not installed on this device", error_code="INSTAGRAM_NOT_INSTALLED")
                return False
            
            # Launch Instagram
            if not self._app.launch():
                send_error("Failed to launch Instagram", error_code="INSTAGRAM_LAUNCH_FAILED")
                return False
            
            send_status("instagram_ready", "Instagram launched successfully")
            return True
            
        except Exception as e:
            error_msg = str(e)
            if "uiautomator" in error_msg.lower() or "atx" in error_msg.lower():
                send_error(f"UIAutomator2 connection failed: {error_msg}", error_code="ATX_AGENT_FAILED")
            else:
                send_error(f"Failed to launch Instagram: {error_msg}", error_code="INSTAGRAM_LAUNCH_FAILED")
            logger.exception("Instagram launch failed")
            return False
    
    def _build_action_config(self, action_type: str, interaction_type: str, primary_target: str,
                              target_list: list, max_profiles: int, min_likes_per_profile: int,
                              max_likes_per_profile: int, like_percentage: int, follow_percentage: int,
                              comment_percentage: int, story_percentage: int, story_like_percentage: int) -> dict:
        """Build action configuration based on action type."""
        
        # Configuration spécifique pour le workflow SYNC_FOLLOWING
        if action_type == 'sync_following':
            return {
                "type": "sync_following",
            }
        
        # Configuration spécifique pour le workflow SYNC_FOLLOWERS_FOLLOWING
        if action_type == 'sync_followers_following':
            sync_cfg = self.config.get('sync', {})
            return {
                "type": "sync_followers_following",
                "mode": sync_cfg.get('mode', 'fast'),
            }
        
        # Configuration spécifique pour le workflow UNFOLLOW
        if action_type == 'unfollow':
            # Utiliser les paramètres spécifiques unfollow s'ils existent
            unfollow_cfg = self.unfollow_config if hasattr(self, 'unfollow_config') else {}
            return {
                "type": "unfollow",
                "max_unfollows": unfollow_cfg.get('maxUnfollows', max_profiles),
                "unfollow_mode": unfollow_cfg.get('unfollowMode', 'non-followers'),
                "min_delay": 2,
                "max_delay": 5,
                "skip_verified": unfollow_cfg.get('skipVerified', True),
                "skip_business": unfollow_cfg.get('skipBusiness', False),
                "min_days_since_follow": unfollow_cfg.get('minDaysSinceFollow', 3),
                "bot_follows_only": unfollow_cfg.get('botFollowsOnly', False),
                "whitelist": unfollow_cfg.get('whitelist', []),
                "blacklist": unfollow_cfg.get('blacklist', []),
            }
        
        # Configuration spécifique pour le workflow FEED
        if action_type == 'feed':
            feed_filters = self.filters or {}
            return {
                "type": "feed",
                "max_interactions": max_profiles,
                "like_percentage": like_percentage,
                "follow_percentage": follow_percentage,
                "comment_percentage": comment_percentage,
                "story_watch_percentage": story_percentage,
                "min_post_likes": feed_filters.get('minPostLikes', 0),
                "max_post_likes": feed_filters.get('maxPostLikes', 0),
                "custom_comments": self.comments_config.get('customComments', [])
            }
        
        # Configuration spécifique pour le workflow NOTIFICATIONS
        if action_type == 'notifications':
            return {
                "type": "notifications",
                "max_interactions": max_profiles,
                "like_percentage": like_percentage,
                "follow_percentage": follow_percentage,
                "comment_percentage": comment_percentage
            }
        
        # Configuration par défaut pour les autres workflows (interact_with_followers, hashtag, post_url)
        return {
            "type": action_type,
            "target_username": primary_target if action_type == 'interact_with_followers' else None,
            "target_usernames": target_list if action_type == 'interact_with_followers' else [],
            "hashtag": self.target if action_type == 'hashtag' else None,
            "post_url": self.target if action_type == 'post_url' else None,
            "interaction_type": interaction_type,
            "max_interactions": max_profiles,
            "like_posts": True,
            "min_likes_per_profile": min_likes_per_profile,
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
            "comment_settings": {
                "enabled": comment_percentage > 0,
                "custom_comments": self.comments_config.get('customComments', [])
            },
            "scrolling": {
                "enabled": True,
                "max_scroll_attempts": 3,
                "scroll_delay": 1.5
            }
        }
    
    def build_workflow_config(self) -> dict:
        """Build the workflow configuration matching CLI format."""
        max_profiles = self.limits.get('maxProfiles', 20)
        min_likes_per_profile = self.limits.get('minLikesPerProfile', 1)
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
        elif self.workflow_type == 'unfollow':
            interaction_type = 'unfollow'
            action_type = 'unfollow'
            session_workflow_type = 'unfollow'
        elif self.workflow_type == 'sync_following':
            interaction_type = 'sync_following'
            action_type = 'sync_following'
            session_workflow_type = 'sync_following'
        elif self.workflow_type == 'sync_followers_following':
            interaction_type = 'sync_followers_following'
            action_type = 'sync_followers_following'
            session_workflow_type = 'sync_following'
        elif self.workflow_type == 'feed':
            interaction_type = 'feed'
            action_type = 'feed'
            session_workflow_type = 'feed'
        elif self.workflow_type == 'notifications':
            interaction_type = 'notifications'
            action_type = 'notifications'
            session_workflow_type = 'notifications'
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
                "total_likes_limit": math.ceil(max_profiles * max_likes_per_profile * (like_percentage / 100)) if like_percentage > 0 else 0,  # use max as upper bound
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
                self._build_action_config(
                    action_type=action_type,
                    interaction_type=interaction_type,
                    primary_target=primary_target,
                    target_list=target_list,
                    max_profiles=max_profiles,
                    min_likes_per_profile=min_likes_per_profile,
                    max_likes_per_profile=max_likes_per_profile,
                    like_percentage=like_percentage,
                    follow_percentage=follow_percentage,
                    comment_percentage=comment_percentage,
                    story_percentage=story_percentage,
                    story_like_percentage=story_like_percentage
                )
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
            
            # Send structured session config for WorkflowAnalyzer
            send_message("session_config", config={
                "deviceId": self.device_id,
                "workflowType": self.workflow_type,
                "target": self.target,
                "limits": {
                    "maxProfiles": self.limits.get('maxProfiles', 20),
                    "maxLikesPerProfile": self.limits.get('maxLikesPerProfile', 2)
                },
                "probabilities": {
                    "like": self.probabilities.get('like', 80),
                    "follow": self.probabilities.get('follow', 20),
                    "comment": self.probabilities.get('comment', 5),
                    "watchStories": self.probabilities.get('watchStories', 15),
                    "likeStories": self.probabilities.get('likeStories', 10)
                },
                "filters": {
                    "minFollowers": self.filters.get('minFollowers', 50),
                    "maxFollowers": self.filters.get('maxFollowers', 50000),
                    "minPosts": self.filters.get('minPosts', 5),
                    "maxFollowing": self.filters.get('maxFollowing', 7500)
                },
                "session": {
                    "durationMinutes": self.session_config.get('durationMinutes', 60),
                    "minDelay": self.session_config.get('minDelay', 5),
                    "maxDelay": self.session_config.get('maxDelay', 15)
                },
                **({"ai": {
                    "enabled": True,
                    "smartComments": self.ai_config.get('smartComments', False),
                    "profileAnalysis": self.ai_config.get('profileAnalysis', False),
                    "postAnalysis": self.ai_config.get('postAnalysis', False),
                }} if self.ai_enabled else {})
            })
            
            # Create automation instance (matching CLI usage)
            send_status("initializing", "Initializing automation...")
            self.automation = InstagramAutomation(self.device_manager)
            
            # Apply config
            self.automation.config = workflow_config
            # Propagate clone package name so helpers can use it
            self.automation.package_name = self.package_name or "com.instagram.android"
            # Also set the global registry so deep-link navigation etc. can resolve it
            from taktik.core.clone import set_active_package
            set_active_package(self.automation.package_name)
            send_log("info", "Dynamic config applied")
            
            # Detect installed app version and apply selector overrides
            try:
                detected_version = self._app.get_installed_version() if self._app else None
                if detected_version:
                    from taktik.core.compat.setup import apply_version_overrides
                    patched = apply_version_overrides("instagram", detected_version)
                    if patched > 0:
                        send_log("info", f"Applied {patched} selector override(s) for Instagram v{detected_version}")
                    else:
                        send_log("info", f"Instagram v{detected_version}: no selector overrides needed")
            except Exception as e:
                send_log("warning", f"Version override failed (non-fatal): {e}")

            # Patch selectors for clone package (must run AFTER version overrides)
            if self.package_name:
                try:
                    from taktik.core.clone import patch_selectors_for_package
                    patched_clone = patch_selectors_for_package("instagram", self.package_name)
                    if patched_clone > 0:
                        send_log("info", f"Patched {patched_clone} selector(s) for clone: {self.package_name}")
                except Exception as e:
                    send_log("warning", f"Clone selector patching failed (non-fatal): {e}")

            # Detect app language and optimize selectors
            try:
                from taktik.core.social_media.instagram.ui.language import detect_and_optimize
                detected_lang = detect_and_optimize(self.automation.device)
                send_log("info", f"App language detected: {detected_lang.upper()}")
            except Exception as e:
                send_log("warning", f"Language detection failed (non-fatal): {e}")
            
            # ── AI hooks (monkey-patch interaction engine if AI mode is ON) ──
            if self.ai_enabled and self.ai_service:
                self._install_ai_hooks()
            
            # Run the workflow
            send_status("running", "Running workflow...")
            self.automation.run_workflow()
            
            # Get final stats
            stats = self.automation.stats
            send_stats(
                likes=stats.get('likes', 0),
                follows=stats.get('follows', 0),
                comments=stats.get('comments', 0),
                profiles=stats.get('interactions', 0),
                unfollows=stats.get('unfollows', 0)
            )
            
            send_status("completed", "Workflow completed successfully")
            return True
                
        except Exception as e:
            error_msg = str(e)
            if "uiautomator" in error_msg.lower() or "atx" in error_msg.lower():
                send_error(f"UIAutomator2 crashed during workflow: {error_msg}", error_code="ATX_AGENT_CRASHED")
            elif "timeout" in error_msg.lower():
                send_error(f"Workflow timed out: {error_msg}", error_code="WORKFLOW_TIMEOUT")
            else:
                send_error(f"Workflow error: {error_msg}", error_code="WORKFLOW_ERROR")
            logger.exception("Workflow error")
            return False
    
    def _crop_screenshot_to_post(self, img, device):
        """
        Crop a full-screen screenshot to the currently visible post area.

        Strategy:
        1. Find the post header (username row) as crop_top boundary
        2. Find the like/comment button row as crop_bottom boundary
        3. Falls back to full image if neither found

        This ensures the vision AI only sees the target post, not adjacent posts.
        """
        try:
            width, height = img.size

            crop_top = None
            crop_bottom = None

            # ── Top boundary: post header row (profile name/avatar) ──────────
            header_selectors = [
                '//*[@resource-id="com.instagram.android:id/row_feed_profile_header"]',
                '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
                '//*[@resource-id="com.instagram.android:id/clips_author_info"]',
            ]
            for sel in header_selectors:
                try:
                    el = device.xpath(sel)
                    if el.exists:
                        b = el.info.get('bounds', {})
                        if b and b.get('top', 0) >= 0:
                            crop_top = max(0, b.get('top', 0) - 8)
                            break
                except Exception:
                    continue

            # ── Bottom boundary: like/comment buttons row ─────────────────────
            buttons_selectors = [
                '//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]',
                '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]',
                '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]',
            ]
            for sel in buttons_selectors:
                try:
                    el = device.xpath(sel)
                    if el.exists:
                        b = el.info.get('bounds', {})
                        if b and b.get('bottom', 0) > 0:
                            crop_bottom = min(height, b.get('bottom', height) + int(height * 0.03))
                            break
                except Exception:
                    continue

            # ── Apply crop if we have at least one boundary ───────────────────
            if crop_top is not None and crop_bottom is not None:
                if crop_bottom > crop_top + 50:
                    return img.crop((0, crop_top, width, crop_bottom))
            elif crop_bottom is not None:
                # Only bottom known — estimate top from button position
                crop_top = max(0, crop_bottom - int(height * 0.70))
                return img.crop((0, crop_top, width, crop_bottom))

        except Exception:
            pass
        return img

    def _install_ai_hooks(self):
        """
        Monkey-patch the workflow's interaction engine to inject AI capabilities:
        1. Smart Comments — replace random/custom comments with AI-generated ones
        2. Profile Analysis — classify each visited profile via vision AI
        3. Post Analysis — analyze post content before commenting
        """
        import tempfile
        import os

        ai = self.ai_service
        ai_cfg = self.ai_config
        device = self.device_manager.device if self.device_manager else None
        bridge = self

        if not device:
            send_log("warning", "AI hooks: no device available, skipping")
            return

        # ── 1. Smart Comments hook ─────────────────────────────────────────
        if ai_cfg.get('smartComments', False):
            try:
                from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction
                _original_comment_on_post = CommentAction.comment_on_post

                def _ai_comment_on_post(self_comment, comment_text=None, template_category='generic',
                                        custom_comments=None, config=None, username=None):
                    """AI-enhanced comment_on_post: generate smart comment if no text provided."""
                    if comment_text:
                        # Explicit text provided — use as-is
                        return _original_comment_on_post(
                            self_comment, comment_text=comment_text,
                            template_category=template_category,
                            custom_comments=custom_comments, config=config, username=username
                        )

                    # Take screenshot of current post for context (cropped to post area only)
                    try:
                        tmp_dir = os.path.join(tempfile.gettempdir(), 'taktik_ai')
                        os.makedirs(tmp_dir, exist_ok=True)
                        screenshot_path = os.path.join(tmp_dir, f'post_{username or "unknown"}.png')
                        img = device.screenshot()  # PIL Image
                        img = bridge._crop_screenshot_to_post(img, device)
                        img.save(screenshot_path, format='PNG')

                        # Post analysis REQUIRED for smart comments — without it the text model
                        # has no visual context and will refuse/generate useless responses
                        post_desc = ""
                        if ai_cfg.get('postAnalysis', False):
                            analysis = ai.analyze_post(screenshot_path, username=username)
                            if analysis.get('success'):
                                post_desc = analysis['description']
                            else:
                                send_log("warning", f"Post analysis failed for @{username}: {analysis.get('error')}")

                        # No description available — cancel comment entirely
                        # (user chose AI comments, no custom fallback expected)
                        if not post_desc:
                            send_log("info", f"No post description for @{username}, skipping comment (AI mode)")
                            return False

                        lang = bridge.language if bridge.language != 'en' else 'auto'
                        result = ai.generate_smart_comment(
                            post_description=post_desc,
                            username=username or 'unknown',
                            niche='general',
                            language=lang,
                        )
                        if result.get('success') and result.get('comment'):
                            ai_comment = result['comment']
                            # Reject model refusals / error messages — they're too long and useless
                            refusal_signals = [
                                "i can't", "i cannot", "i'm unable", "i am unable",
                                "without seeing", "without the image", "without viewing",
                                "no image", "can't see", "cannot see", "don't have access",
                                "do not have access", "provide an image", "share the image",
                                "specific post", "specific content",
                            ]
                            ai_comment_lower = ai_comment.lower()
                            is_refusal = len(ai_comment) > 120 or any(sig in ai_comment_lower for sig in refusal_signals)
                            if is_refusal:
                                send_log("warning", f"AI comment refused/unusable for @{username} (model couldn't see post), skipping comment")
                                return False
                            send_log("info", f"🤖 AI comment for @{username}: \"{ai_comment}\"")
                            return _original_comment_on_post(
                                self_comment, comment_text=ai_comment,
                                template_category=template_category,
                                custom_comments=None, config=config, username=username
                            )
                        else:
                            send_log("warning", f"AI comment generation failed, falling back to default")
                    except Exception as e:
                        send_log("warning", f"AI comment hook error: {e}")

                    # Fallback to original behavior
                    return _original_comment_on_post(
                        self_comment, comment_text=comment_text,
                        template_category=template_category,
                        custom_comments=custom_comments, config=config, username=username
                    )

                CommentAction.comment_on_post = _ai_comment_on_post
                send_log("info", "✅ AI Smart Comments hook installed")
            except Exception as e:
                send_log("warning", f"Failed to install Smart Comments hook: {e}")

        # ── 2. Profile Analysis hook ───────────────────────────────────────
        if ai_cfg.get('profileAnalysis', False):
            try:
                from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import InteractionEngineMixin
                _original_perform = InteractionEngineMixin._perform_interactions_on_profile

                def _ai_perform_interactions(self_engine, username, config, profile_data=None):
                    """AI-enhanced: classify profile before interacting."""
                    try:
                        tmp_dir = os.path.join(tempfile.gettempdir(), 'taktik_ai')
                        os.makedirs(tmp_dir, exist_ok=True)
                        screenshot_path = os.path.join(tmp_dir, f'profile_{username}.png')
                        img = device.screenshot()  # PIL Image
                        img.save(screenshot_path, format='PNG')

                        account_username = None
                        if bridge.automation:
                            account_username = bridge.automation.active_username

                        classification = ai.classify_profile(
                            username=username,
                            screenshot_path=screenshot_path,
                            account_username=account_username,
                        )
                        if classification.get('success') and classification.get('classification'):
                            c = classification['classification']
                            send_log("info", f"🧠 @{username}: [{c.get('niche_category', '?')}] {c.get('niche', '?')} — Score: {c.get('score', 0)}/100")
                    except Exception as e:
                        send_log("warning", f"AI profile analysis error for @{username}: {e}")

                    # Always proceed with original interaction logic
                    return _original_perform(self_engine, username, config, profile_data)

                InteractionEngineMixin._perform_interactions_on_profile = _ai_perform_interactions
                send_log("info", "✅ AI Profile Analysis hook installed")
            except Exception as e:
                send_log("warning", f"Failed to install Profile Analysis hook: {e}")

        # ── 3. Post Analysis hook (standalone, if no smart comments) ───────
        # Post analysis is already integrated into the smart comment hook above.
        # If smart comments are OFF but post analysis is ON, we install a separate
        # hook on the like orchestration to analyze posts before liking.
        if ai_cfg.get('postAnalysis', False) and not ai_cfg.get('smartComments', False):
            try:
                from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import LikeOrchestration
                _original_like_current = LikeOrchestration.like_current_post

                def _ai_like_current_post(self_like):
                    """AI-enhanced: analyze post before liking."""
                    try:
                        tmp_dir = os.path.join(tempfile.gettempdir(), 'taktik_ai')
                        os.makedirs(tmp_dir, exist_ok=True)
                        screenshot_path = os.path.join(tmp_dir, f'post_like_{id(self_like)}.png')
                        img = device.screenshot()  # PIL Image
                        img = bridge._crop_screenshot_to_post(img, device)
                        img.save(screenshot_path, format='PNG')
                        ai.analyze_post(screenshot_path)
                    except Exception as e:
                        send_log("warning", f"AI post analysis before like error: {e}")
                    return _original_like_current(self_like)

                LikeOrchestration.like_current_post = _ai_like_current_post
                send_log("info", "✅ AI Post Analysis hook installed")
            except Exception as e:
                send_log("warning", f"Failed to install Post Analysis hook: {e}")

        send_log("info", f"🤖 AI hooks installed: smartComments={ai_cfg.get('smartComments')}, profileAnalysis={ai_cfg.get('profileAnalysis')}, postAnalysis={ai_cfg.get('postAnalysis')}")

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
        # Setup stats IPC callback before any workflow runs
        setup_stats_callback()
        
        config = None
        
        # Check for --debug flag first (for debug commands)
        if len(sys.argv) >= 2 and sys.argv[1] == '--debug':
            # Debug mode: --debug --mode analyze/detect --device <device_id>
            import argparse
            parser = argparse.ArgumentParser()
            parser.add_argument('--debug', action='store_true')
            parser.add_argument('--mode', choices=['analyze', 'detect'], default='analyze')
            parser.add_argument('--device', type=str, required=True)
            args = parser.parse_args()
            
            config = {
                'debugMode': True,
                'mode': args.mode,
                'deviceId': args.device
            }
            
            bridge = DebugBridge(config)
            exit_code = bridge.run()
            sys.exit(exit_code)
        
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
        
        # Check if this is a debug command via JSON config
        if config.get('debugMode'):
            bridge = DebugBridge(config)
            exit_code = bridge.run()
            sys.exit(exit_code)
        
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
