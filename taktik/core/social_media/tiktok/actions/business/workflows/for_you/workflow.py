"""For You Feed Workflow for TikTok automation.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

Ce workflow permet d'automatiser les interactions sur le feed For You:
- Scroller les vidéos
- Liker les vidéos selon des critères
- Suivre les créateurs selon des filtres
- Extraire les informations des vidéos
"""

from typing import Optional, Dict, Any
import time
import random

from .._internal import BaseVideoWorkflow, VideoWorkflowStats, FeedInterruptionsMixin
from .models import ForYouConfig


# Backward-compat alias
ForYouStats = VideoWorkflowStats


class ForYouWorkflow(FeedInterruptionsMixin, BaseVideoWorkflow):
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
            # Navigate to For You feed
            # Note: TikTok restart is handled by the bridge's tiktok_startup()
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
    
    # _handle_suggestion_page and _handle_comments_section are provided
    # by FeedInterruptionsMixin. The mixin reads self.config.follow_back_suggestions
    # automatically (defaults to False if the attribute is absent).
    
