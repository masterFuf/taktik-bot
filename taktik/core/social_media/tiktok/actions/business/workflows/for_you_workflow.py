"""For You Feed Workflow for TikTok automation.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

Ce workflow permet d'automatiser les interactions sur le feed For You:
- Scroller les vidéos
- Liker les vidéos selon des critères
- Suivre les créateurs selon des filtres
- Extraire les informations des vidéos
"""

from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from loguru import logger
import time
import random

from ...atomic.click_actions import ClickActions
from ...atomic.navigation_actions import NavigationActions
from ...atomic.scroll_actions import ScrollActions
from ...atomic.detection_actions import DetectionActions


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


@dataclass
class ForYouStats:
    """Statistiques du workflow For You."""
    
    videos_watched: int = 0
    videos_liked: int = 0
    users_followed: int = 0
    videos_favorited: int = 0
    videos_skipped: int = 0
    ads_skipped: int = 0  # Publicités passées
    popups_closed: int = 0  # Popups fermées
    suggestions_handled: int = 0  # Pages de suggestion gérées
    errors: int = 0
    
    start_time: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        elapsed = time.time() - self.start_time
        return {
            'videos_watched': self.videos_watched,
            'videos_liked': self.videos_liked,
            'users_followed': self.users_followed,
            'videos_favorited': self.videos_favorited,
            'videos_skipped': self.videos_skipped,
            'ads_skipped': self.ads_skipped,
            'popups_closed': self.popups_closed,
            'suggestions_handled': self.suggestions_handled,
            'errors': self.errors,
            'elapsed_seconds': elapsed,
            'elapsed_formatted': f"{int(elapsed // 60)}m {int(elapsed % 60)}s",
        }


class ForYouWorkflow:
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
        self.device = device
        self.config = config or ForYouConfig()
        self.stats = ForYouStats()
        
        # Initialize atomic actions
        self.click = ClickActions(device)
        self.navigation = NavigationActions(device)
        self.scroll = ScrollActions(device)
        self.detection = DetectionActions(device)
        
        self.logger = logger.bind(module="tiktok-for-you-workflow")
        
        # Callbacks
        self._on_video_callback: Optional[Callable] = None
        self._on_like_callback: Optional[Callable] = None
        self._on_follow_callback: Optional[Callable] = None
        self._on_stats_callback: Optional[Callable] = None
        self._on_pause_callback: Optional[Callable] = None
        
        # State
        self._running = False
        self._paused = False
        self._actions_since_pause = 0
    
    def set_on_video_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called for each video processed."""
        self._on_video_callback = callback
    
    def set_on_like_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called when a video is liked."""
        self._on_like_callback = callback
    
    def set_on_follow_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called when a user is followed."""
        self._on_follow_callback = callback
    
    def set_on_stats_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called after each action to send real-time stats."""
        self._on_stats_callback = callback
    
    def set_on_pause_callback(self, callback: Callable[[int], None]):
        """Set callback called when workflow takes a pause.
        
        Args:
            callback: Function that receives pause duration in seconds.
        """
        self._on_pause_callback = callback
    
    def _send_stats_update(self):
        """Send current stats via callback."""
        if self._on_stats_callback:
            try:
                self._on_stats_callback(self.stats.to_dict())
            except Exception as e:
                self.logger.warning(f"Error sending stats: {e}")
    
    def stop(self):
        """Stop the workflow."""
        self._running = False
        self.logger.info("🛑 Workflow stop requested")
    
    def pause(self):
        """Pause the workflow."""
        self._paused = True
        self.logger.info("⏸️ Workflow paused")
    
    def resume(self):
        """Resume the workflow."""
        self._paused = False
        self.logger.info("▶️ Workflow resumed")
    
    def run(self) -> ForYouStats:
        """Run the For You workflow.
        
        Returns:
            ForYouStats: Statistics from the workflow run
        """
        self.logger.info("🚀 Starting For You workflow")
        self.logger.info(f"📊 Config: max_videos={self.config.max_videos}, "
                        f"like_prob={self.config.like_probability}, "
                        f"follow_prob={self.config.follow_probability}")
        
        self._running = True
        self.stats = ForYouStats()
        
        try:
            # Force restart TikTok to ensure clean state
            self._restart_tiktok()
            
            # Navigate to For You feed
            if not self._ensure_on_for_you():
                self.logger.error("❌ Failed to navigate to For You feed")
                return self.stats
            
            # Process videos
            while self._running and self.stats.videos_watched < self.config.max_videos:
                # Check if paused
                while self._paused and self._running:
                    time.sleep(1)
                
                if not self._running:
                    break
                
                # Check and close any popups first
                self._handle_popups()
                
                # Check for comments section accidentally opened
                if self._handle_comments_section():
                    continue  # Skip to next iteration after closing comments
                
                # Check for suggestion page (Follow back / Not interested)
                if self._handle_suggestion_page():
                    continue  # Skip to next iteration after handling suggestion
                
                # Check limits
                if self._check_limits_reached():
                    self.logger.info("📊 Session limits reached")
                    break
                
                # Get video info immediately for real-time display
                video_info = self.detection.get_video_info()
                
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
                    # Scroll to next video without processing
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
        """Check if video should be skipped based on filters."""
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
    
    def _decide_and_execute_actions(self, video_info: Dict[str, Any]):
        """Decide and execute actions based on probabilities."""
        # Like
        if (self.stats.videos_liked < self.config.max_likes_per_session and
            random.random() < self.config.like_probability and
            not video_info.get('is_liked')):
            
            if self._like_video(video_info):
                self._actions_since_pause += 1
        
        # Follow
        if (self.stats.users_followed < self.config.max_follows_per_session and
            random.random() < self.config.follow_probability):
            
            if self._follow_user(video_info):
                self._actions_since_pause += 1
        
        # Favorite
        if (random.random() < self.config.favorite_probability and
            not video_info.get('is_favorited')):
            
            if self._favorite_video(video_info):
                self._actions_since_pause += 1
    
    def _like_video(self, video_info: Dict[str, Any]) -> bool:
        """Like the current video."""
        self.logger.info(f"❤️ Liking video by @{video_info.get('author')}")
        
        if self.click.click_like_button():
            self.stats.videos_liked += 1
            self._send_stats_update()  # Real-time stats
            
            if self._on_like_callback:
                try:
                    self._on_like_callback(video_info)
                except Exception as e:
                    self.logger.warning(f"Like callback error: {e}")
            
            return True
        
        return False
    
    def _follow_user(self, video_info: Dict[str, Any]) -> bool:
        """Follow the current video's author."""
        self.logger.info(f"👤 Following @{video_info.get('author')}")
        
        if self.click.click_video_follow_button():
            self.stats.users_followed += 1
            self._send_stats_update()  # Real-time stats
            
            if self._on_follow_callback:
                try:
                    self._on_follow_callback(video_info)
                except Exception as e:
                    self.logger.warning(f"Follow callback error: {e}")
            
            return True
        
        return False
    
    def _favorite_video(self, video_info: Dict[str, Any]) -> bool:
        """Add current video to favorites."""
        self.logger.info(f"⭐ Adding to favorites: @{video_info.get('author')}")
        
        if self.click.click_favorite_button():
            self.stats.videos_favorited += 1
            self._send_stats_update()  # Real-time stats
            return True
        
        return False
    
    def _check_limits_reached(self) -> bool:
        """Check if session limits are reached."""
        if self.stats.videos_liked >= self.config.max_likes_per_session:
            self.logger.info("📊 Max likes per session reached")
            return True
        
        if self.stats.users_followed >= self.config.max_follows_per_session:
            self.logger.info("📊 Max follows per session reached")
            return True
        
        return False
    
    def _check_pause_needed(self):
        """Check if a pause is needed and execute it."""
        if self._actions_since_pause >= self.config.pause_after_actions:
            pause_duration = random.uniform(
                self.config.pause_duration_min,
                self.config.pause_duration_max
            )
            pause_seconds = int(pause_duration)
            self.logger.info(f"⏸️ Taking a break for {pause_seconds}s")
            
            # Send pause callback to frontend
            if self._on_pause_callback:
                try:
                    self._on_pause_callback(pause_seconds)
                except Exception as e:
                    self.logger.warning(f"Error sending pause callback: {e}")
            
            time.sleep(pause_duration)
            self._actions_since_pause = 0
    
    def _is_ad_video(self) -> bool:
        """Check if current video is an advertisement."""
        return self.detection.is_ad_video()
    
    def _handle_popups(self):
        """Check for and close any popups that might block interaction."""
        if self.detection.has_popup():
            self.logger.info("🚨 Popup detected, attempting to close")
            
            # Try to close collections popup specifically
            if self.detection.has_collections_popup():
                if self.click.close_collections_popup():
                    self.stats.popups_closed += 1
                    self.logger.info("✅ Collections popup closed")
                    time.sleep(0.5)
                    return
            
            # Try generic popup close
            if self.click.close_popup():
                self.stats.popups_closed += 1
                self.logger.info("✅ Popup closed")
                time.sleep(0.5)
    
    def _handle_suggestion_page(self) -> bool:
        """Check for and handle suggestion page (Follow back / Not interested).
        
        Returns:
            True if a suggestion page was handled, False otherwise.
        """
        if self.detection.has_suggestion_page():
            self.logger.info("💡 Suggestion page detected")
            
            if self.config.follow_back_suggestions:
                self.logger.info("👤 Following back suggested user")
                if self.click.click_follow_back():
                    self.stats.suggestions_handled += 1
                    self.stats.users_followed += 1
                    self._send_stats_update()
                    time.sleep(1)
                    return True
            else:
                self.logger.info("❌ Clicking 'Not interested'")
                if self.click.click_not_interested():
                    self.stats.suggestions_handled += 1
                    self._send_stats_update()
                    time.sleep(1)
                    return True
            
            # Fallback: try to close via X button
            if self.click.close_suggestion_page():
                self.stats.suggestions_handled += 1
                self._send_stats_update()
                time.sleep(0.5)
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
    
    def _parse_count(self, count_str: str) -> int:
        """Parse count string (e.g., '1.2K', '500', '1M') to integer."""
        if not count_str:
            return 0
        
        count_str = count_str.strip().upper()
        
        try:
            if 'K' in count_str:
                return int(float(count_str.replace('K', '')) * 1000)
            elif 'M' in count_str:
                return int(float(count_str.replace('M', '')) * 1000000)
            elif 'B' in count_str:
                return int(float(count_str.replace('B', '')) * 1000000000)
            else:
                # Remove commas and parse
                return int(count_str.replace(',', '').replace('.', ''))
        except (ValueError, AttributeError):
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current workflow statistics."""
        return self.stats.to_dict()
