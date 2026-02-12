"""For You Feed Workflow for TikTok automation.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

Ce workflow permet d'automatiser les interactions sur le feed For You:
- Scroller les vidéos
- Liker les vidéos selon des critères
- Suivre les créateurs selon des filtres
- Extraire les informations des vidéos
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import time
import random

from .._internal import BaseVideoWorkflow, VideoWorkflowStats


@dataclass
class ForYouConfig:
    """Configuration pour le workflow For You."""
    
    # Nombre de vidéos à traiter
    max_videos: int = 50
    
    # Temps de visionnage (secondes)
    min_watch_time: float = 2.0
    max_watch_time: float = 8.0
    
    # Probabilités d'action (0.0 à 1.0)
    like_probability: float = 0.3
    follow_probability: float = 0.1
    favorite_probability: float = 0.05
    
    # Filtres
    min_likes: Optional[int] = None  # Minimum de likes pour interagir
    max_likes: Optional[int] = None  # Maximum de likes pour interagir
    required_hashtags: List[str] = field(default_factory=list)  # Hashtags requis
    excluded_hashtags: List[str] = field(default_factory=list)  # Hashtags exclus
    
    # Limites de session
    max_likes_per_session: int = 50
    max_follows_per_session: int = 20
    
    # Pauses
    pause_after_actions: int = 10  # Pause après N actions
    pause_duration_min: float = 30.0
    pause_duration_max: float = 60.0
    
    # Comportement
    skip_already_liked: bool = True
    skip_already_followed: bool = True
    skip_ads: bool = True  # Skip les publicités automatiquement
    follow_back_suggestions: bool = False  # Si True, follow back les suggestions. Si False, click "Not interested"


# Backward-compat alias
ForYouStats = VideoWorkflowStats


class ForYouWorkflow(BaseVideoWorkflow):
    """Workflow d'automatisation du feed For You TikTok.
    
    Ce workflow permet de:
    - Naviguer vers le feed For You
    - Scroller les vidéos avec un temps de visionnage variable
    - Liker/Follow/Favoriser selon des probabilités et filtres
    - Extraire les informations des vidéos
    - Respecter les limites et pauses
    """
    
    def __init__(self, device, config: Optional[ForYouConfig] = None):
        """Initialize the workflow.
        
        Args:
            device: Device facade for UI interactions
            config: Optional configuration, uses defaults if not provided
        """
        super().__init__(device, module_name="tiktok-for-you-workflow")
        self.config = config or ForYouConfig()
        self.stats = VideoWorkflowStats()
    
    def run(self) -> VideoWorkflowStats:
        """Run the For You workflow.
        
        Returns:
            VideoWorkflowStats: Statistics from the workflow run
        """
        self.logger.info("🚀 Starting For You workflow")
        self.logger.info(f"📊 Config: max_videos={self.config.max_videos}, "
                        f"like_prob={self.config.like_probability}, "
                        f"follow_prob={self.config.follow_probability}")
        
        self._running = True
        self.stats = VideoWorkflowStats()
        
        try:
            # Force restart TikTok to ensure clean state
            self._restart_tiktok()
            
            # Navigate to For You feed
            if not self._ensure_on_for_you():
                self.logger.error("❌ Failed to navigate to For You feed")
                return self.stats
            
            # Process videos
            while self._running and self.stats.videos_watched < self.config.max_videos:
                if not self._wait_if_paused():
                    break
                
                # Check and close any popups first
                self._handle_popups()
                
                # Check for comments section accidentally opened
                if self._handle_comments_section():
                    continue
                
                # Check for suggestion page (Follow back / Not interested)
                if self._handle_suggestion_page():
                    continue
                
                # Check limits
                if self._check_limits_reached():
                    self.logger.info("📊 Session limits reached")
                    break
                
                # Get video info immediately for real-time display
                video_info = self.detection.get_video_info()
                
                # Detect stuck state
                if self._handle_stuck_video(video_info):
                    continue
                
                # Send video info callback immediately (before any processing)
                if self._on_video_callback:
                    try:
                        self._on_video_callback(video_info)
                    except Exception as e:
                        self.logger.warning(f"Video callback error: {e}")
                
                # Check if current video is an ad
                if self.config.skip_ads and video_info.get('is_ad', False):
                    self.logger.info("📺 Skipping advertisement")
                    self.stats.ads_skipped += 1
                    self._send_stats_update()
                    if not self.scroll.scroll_to_next_video():
                        self.stats.errors += 1
                    continue
                
                # Process current video (video_info already fetched)
                self._process_current_video(video_info)
                
                # Check for pause
                self._check_pause_needed()
                
                # Scroll to next video
                if not self.scroll.scroll_to_next_video():
                    self.logger.warning("❌ Failed to scroll to next video")
                    if self.click.close_system_popup():
                        self.logger.info("✅ System popup was blocking, closed it")
                        time.sleep(0.5)
                        self.scroll.scroll_to_next_video()
                    else:
                        self.stats.errors += 1
                        if self.stats.errors > 5:
                            self.logger.error("❌ Too many errors, stopping")
                            break
            
            self.logger.success(f"✅ Workflow completed: {self.stats.to_dict()}")
            
        except Exception as e:
            self.logger.error(f"❌ Workflow error: {e}")
            self.stats.errors += 1
        
        finally:
            self._running = False
        
        return self.stats
    
    def _restart_tiktok(self):
        """Force restart TikTok to ensure clean state.
        
        This is called at the beginning of each workflow to ensure
        TikTok starts from a known state (For You feed).
        """
        self.logger.info("🔄 Restarting TikTok for clean state...")
        
        # Force stop and restart TikTok using ADB directly
        try:
            # Get the underlying device to access serial
            underlying_device = self.device._device if hasattr(self.device, '_device') else self.device
            device_serial = getattr(underlying_device, 'serial', None)
            
            if device_serial:
                import subprocess
                
                # Force stop TikTok
                self.logger.info("🛑 Force stopping TikTok...")
                stop_cmd = f'adb -s {device_serial} shell am force-stop com.zhiliaoapp.musically'
                subprocess.run(stop_cmd, shell=True, capture_output=True, timeout=10)
                self.logger.info("✅ TikTok stopped")
                
                # Wait a bit for clean shutdown
                time.sleep(1.5)
                
                # Relaunch TikTok
                self.logger.info("🚀 Relaunching TikTok...")
                launch_cmd = f'adb -s {device_serial} shell am start -n com.zhiliaoapp.musically/com.ss.android.ugc.aweme.splash.SplashActivity'
                subprocess.run(launch_cmd, shell=True, capture_output=True, timeout=10)
                self.logger.info("✅ TikTok relaunched")
                
                # Wait for app to fully load
                time.sleep(4)
            else:
                self.logger.warning("⚠️ Could not get device serial, skipping restart")
                
        except Exception as e:
            self.logger.error(f"❌ Error restarting TikTok: {e}")
            # Try to continue anyway
    
    def _ensure_on_for_you(self) -> bool:
        """Ensure we're on the For You feed."""
        self.logger.debug("📱 Ensuring on For You feed")
        
        # FIRST: Close any popups that might be blocking the screen
        self._handle_popups()
        time.sleep(0.3)
        
        # Check if already on For You
        if self.detection.is_on_for_you_page():
            self.logger.debug("✅ Already on For You")
            return True
        
        # Close popups again in case they appeared
        self._handle_popups()
        
        # Navigate to home
        if not self.navigation.navigate_to_home():
            return False
        
        time.sleep(1)
        
        # Click For You tab if needed
        self.click.click_for_you_tab()
        time.sleep(0.5)
        
        # Close any popups that might have appeared
        self._handle_popups()
        
        return self.detection.is_on_for_you_page()
    
    def _process_current_video(self, video_info: Optional[Dict[str, Any]] = None):
        """Process the current video.
        
        Args:
            video_info: Pre-fetched video info, or None to fetch it now.
        """
        self.logger.debug(f"📹 Processing video #{self.stats.videos_watched + 1}")
        
        # Get video info if not provided
        if video_info is None:
            video_info = self.detection.get_video_info()
            # Send callback if we just fetched it
            if self._on_video_callback:
                try:
                    self._on_video_callback(video_info)
                except Exception as e:
                    self.logger.warning(f"Video callback error: {e}")
        
        self.logger.debug(f"📹 Video: @{video_info.get('author')} - "
                         f"likes: {video_info.get('like_count')}")
        
        # Watch video
        watch_time = random.uniform(self.config.min_watch_time, self.config.max_watch_time)
        self.scroll.watch_video(watch_time)
        
        self.stats.videos_watched += 1
        self._send_stats_update()  # Real-time stats
        
        # Check if should skip
        if self._should_skip_video(video_info):
            self.stats.videos_skipped += 1
            self.logger.debug("⏭️ Skipping video (filters)")
            return
        
        # Decide actions
        self._decide_and_execute_actions(video_info)
    
    def _should_skip_video(self, video_info: Dict[str, Any]) -> bool:
        """Check if video should be skipped based on filters (incl. hashtags)."""
        # Skip if already liked and config says so
        if self.config.skip_already_liked and video_info.get('is_liked'):
            return True
        
        # Check like count filters
        like_count_str = video_info.get('like_count', '')
        if like_count_str:
            like_count = self._parse_count(like_count_str)
            
            if self.config.min_likes and like_count < self.config.min_likes:
                return True
            
            if self.config.max_likes and like_count > self.config.max_likes:
                return True
        
        # Check hashtag filters
        description = video_info.get('description', '') or ''
        
        # Required hashtags
        if self.config.required_hashtags:
            has_required = any(
                f"#{tag.lower()}" in description.lower() 
                for tag in self.config.required_hashtags
            )
            if not has_required:
                return True
        
        # Excluded hashtags
        if self.config.excluded_hashtags:
            has_excluded = any(
                f"#{tag.lower()}" in description.lower() 
                for tag in self.config.excluded_hashtags
            )
            if has_excluded:
                return True
        
        return False
    
    def _is_ad_video(self) -> bool:
        """Check if current video is an advertisement."""
        return self.detection.is_ad_video()
    
    def _handle_suggestion_page(self) -> bool:
        """Check for and handle suggestion page (Follow back / Not interested).
        
        Returns:
            True if a suggestion page was handled, False otherwise.
        """
        if self.detection.has_suggestion_page():
            self.logger.info("💡 Suggestion page detected")
            
            handled = False
            
            if self.config.follow_back_suggestions:
                self.logger.info("👤 Following back suggested user")
                if self.click.click_follow_back():
                    self.stats.suggestions_handled += 1
                    self.stats.users_followed += 1
                    self._send_stats_update()
                    time.sleep(1)
                    handled = True
            else:
                self.logger.info("❌ Clicking 'Not interested'")
                if self.click.click_not_interested():
                    self.stats.suggestions_handled += 1
                    self._send_stats_update()
                    time.sleep(1)
                    handled = True
            
            # Fallback: try to close via X button
            if not handled:
                if self.click.close_suggestion_page():
                    self.stats.suggestions_handled += 1
                    self._send_stats_update()
                    time.sleep(0.5)
                    handled = True
            
            # Ultimate fallback: swipe up to skip (as indicated by "Swipe up to skip" text)
            if not handled:
                self.logger.info("⬆️ Swiping up to skip suggestion page")
                self.scroll.scroll_to_next_video()
                self.stats.suggestions_handled += 1
                self._send_stats_update()
                time.sleep(1)
                return True
            
            # After handling, also swipe up to ensure we move to next video
            # The suggestion page sometimes stays even after clicking buttons
            if handled:
                time.sleep(0.5)
                # Check if still on suggestion page
                if self.detection.has_suggestion_page():
                    self.logger.info("⬆️ Still on suggestion page, swiping up")
                    self.scroll.scroll_to_next_video()
                    time.sleep(1)
            
            return True
        
        return False
    
    def _handle_comments_section(self) -> bool:
        """Check for and close comments section if accidentally opened.
        
        This can happen when scrolling and accidentally clicking on the comment input area.
        
        Returns:
            True if comments section was detected and closed, False otherwise.
        """
        if self.detection.has_comments_section_open():
            self.logger.info("💬 Comments section detected, closing...")
            
            if self.click.close_comments_section():
                self.logger.info("✅ Comments section closed")
                time.sleep(0.5)
                return True
            else:
                self.logger.warning("⚠️ Failed to close comments section")
        
        return False
    
