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
from typing import Dict, Any

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
    send_profile_captured, send_profile_skipped,
    send_scraping_profile_visit, send_scraping_dq_progress,
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
            
            from taktik.core.shared.device.manager import DeviceManager
            send_log("debug", "DeviceManager imported successfully")
            
            if not self.device_id:
                send_error("Device ID is required")
                return 1
            
            send_log("debug", f"Connecting to device {self.device_id}...")
            device_manager = DeviceManager(device_id=self.device_id)
            if not device_manager.connect(verify_atx=False):
                send_error(f"Failed to connect to device {self.device_id}")
                return 2
            device = device_manager.device
            
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
        self.feed_stories_config = config.get('feedStories', {})
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
        
        # Network reset configuration
        self.network_reset_config = config.get('networkReset', {})
        self.network_reset_enabled = self.network_reset_config.get('enabled', False)
        self.network_reset_method = self.network_reset_config.get('method', 'data')  # 'data' or 'airplane'
        if self.ai_enabled:
            api_key = self.ai_config.get('openrouterApiKey', '')
            if api_key and len(api_key) > 5:
                from taktik.core.app.ai.providers.openrouter import AIService
                vision_model = self.ai_config.get('visionModel') or None
                self.ai_service = AIService(api_key=api_key, ipc=_ipc, vision_model=vision_model)
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
    
    def build_workflow_config(self) -> dict:
        """Build the workflow configuration matching CLI format."""
        from taktik.core.social_media.instagram.workflows.core.config_builder import (
            build_instagram_automation_config,
        )

        return build_instagram_automation_config(self.config)
    
    def run_workflow(self) -> bool:
        """Run the configured workflow."""
        try:
            from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation
            
            workflow_config = self.build_workflow_config()
            
            # Parse targets for display
            targets_display = ', @'.join([t.strip() for t in self.target.split(',') if t.strip()])
            send_status("starting", f"Starting {self.workflow_type} workflow for @{targets_display}")
            send_log("info", f"Configuration: {json.dumps(workflow_config, indent=2)}")

            from taktik.core.social_media.instagram.workflows.core.config_builder import (
                build_instagram_session_config_event,
            )

            send_message(
                "session_config",
                config=build_instagram_session_config_event(
                    self.config,
                    ai_enabled=self.ai_enabled,
                ),
            )
            
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
                    from taktik.core.compat.selectors.setup import apply_version_overrides
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
                from taktik.core.social_media.instagram.workflows.core.ai_hooks import (
                    install_instagram_ai_hooks,
                )

                install_instagram_ai_hooks(
                    ai=self.ai_service,
                    ai_config=self.ai_config,
                    device=self.device_manager.device if self.device_manager else None,
                    language=self.language,
                    log=send_log,
                )
            
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
    
    def start_media_capture(self) -> bool:
        """Start the media capture service for intercepting Instagram images."""
        if not self.media_capture_enabled:
            send_log("info", "Media capture disabled in config")
            return True
        
        try:
            from taktik.core.social_media.instagram.media import MediaCaptureService
            
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
        
        # Network reset (get new IP before session)
        if self.network_reset_enabled:
            from bridges.common.network import perform_network_reset
            perform_network_reset(self.device_id, method=self.network_reset_method, ipc=_ipc)
        
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
            # Always stop media capture and close Instagram app
            self.stop_media_capture()
            if self._app:
                try:
                    self._app.stop()
                except Exception:
                    pass
        
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
