"""Search/Target Workflow for TikTok automation.

Dernière mise à jour: 11 janvier 2026
Basé sur les UI dumps réels de TikTok.

Ce workflow permet d'automatiser les interactions sur les vidéos trouvées via recherche:
- Rechercher un terme (hashtag, username, keyword)
- Cliquer sur l'onglet Videos
- Ouvrir la première vidéo
- Scroller et interagir avec les vidéos (like, follow, favorite)
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
class SearchConfig:
    """Configuration pour le workflow Search/Target."""
    
    # Search query (required)
    search_query: str = ""
    
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
    min_likes: Optional[int] = None
    max_likes: Optional[int] = None
    
    # Limites de session
    max_likes_per_session: int = 50
    max_follows_per_session: int = 20
    
    # Pauses
    pause_after_actions: int = 10
    pause_duration_min: float = 30.0
    pause_duration_max: float = 60.0
    
    # Comportement
    skip_already_liked: bool = True
    skip_already_followed: bool = True
    skip_ads: bool = True


@dataclass
class SearchStats:
    """Statistiques du workflow Search/Target."""
    
    videos_watched: int = 0
    videos_liked: int = 0
    users_followed: int = 0
    videos_favorited: int = 0
    videos_skipped: int = 0
    ads_skipped: int = 0
    popups_closed: int = 0
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
            'errors': self.errors,
            'elapsed_seconds': elapsed,
            'elapsed_formatted': f"{int(elapsed // 60)}m {int(elapsed % 60)}s",
        }


class SearchWorkflow:
    """Workflow d'automatisation de recherche TikTok.
    
    Ce workflow permet de:
    - Rechercher un terme (hashtag, username, keyword)
    - Naviguer vers les vidéos correspondantes
    - Scroller et interagir avec les vidéos
    - Respecter les limites et pauses
    """
    
    def __init__(self, device, config: Optional[SearchConfig] = None):
        """Initialize the workflow.
        
        Args:
            device: Device facade for UI interactions
            config: Optional configuration, uses defaults if not provided
        """
        self.device = device
        self.config = config or SearchConfig()
        self.stats = SearchStats()
        
        # Initialize atomic actions
        self.click = ClickActions(device)
        self.navigation = NavigationActions(device)
        self.scroll = ScrollActions(device)
        self.detection = DetectionActions(device)
        
        self.logger = logger.bind(module="tiktok-search-workflow")
        
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
        """Set callback called when workflow takes a pause."""
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
    
    def run(self) -> SearchStats:
        """Run the Search workflow.
        
        Returns:
            SearchStats: Statistics from the workflow run
        """
        if not self.config.search_query:
            self.logger.error("❌ No search query provided")
            return self.stats
        
        self.logger.info(f"🚀 Starting Search workflow for: {self.config.search_query}")
        self.logger.info(f"📊 Config: max_videos={self.config.max_videos}, "
                        f"like_prob={self.config.like_probability}, "
                        f"follow_prob={self.config.follow_probability}")
        
        self._running = True
        self.stats = SearchStats()
        
        try:
            # Navigate to search and open videos
            if not self._navigate_to_search_videos():
                self.logger.error("❌ Failed to navigate to search videos")
                return self.stats
            
            # Track last video to detect stuck state
            last_video_author = None
            same_video_count = 0
            
            # Process videos
            while self._running and self.stats.videos_watched < self.config.max_videos:
                # Check if paused
                while self._paused and self._running:
                    time.sleep(1)
                
                if not self._running:
                    break
                
                # Check and close any popups first
                self._handle_popups()
                
                # Check limits
                if self._check_limits_reached():
                    self.logger.info("📊 Session limits reached")
                    break
                
                # Get video info
                video_info = self.detection.get_video_info()
                
                # Detect stuck state (same video appearing multiple times)
                current_author = video_info.get('author', '')
                current_likes = video_info.get('like_count', '')
                video_signature = f"{current_author}_{current_likes}"
                
                if video_signature == last_video_author and current_author:
                    same_video_count += 1
                    self.logger.warning(f"⚠️ Same video detected {same_video_count} times: @{current_author}")
                    
                    if same_video_count >= 3:
                        self.logger.error("🚨 Stuck on same video! Checking for blocking popups...")
                        # Aggressive popup clearing
                        self.click.close_system_popup()
                        time.sleep(0.3)
                        self._handle_popups()
                        time.sleep(0.3)
                        # Press back to clear any overlay
                        self.device.press("back")
                        time.sleep(0.5)
                        same_video_count = 0
                        continue  # Skip processing and try again
                else:
                    same_video_count = 0
                    last_video_author = video_signature
                
                # Send video info callback
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
                    self._scroll_to_next()
                    continue
                
                # Check if should skip this video
                if self._should_skip_video(video_info):
                    self.logger.debug(f"⏭️ Skipping video by @{video_info.get('author')}")
                    self.stats.videos_skipped += 1
                    self._send_stats_update()
                    self._scroll_to_next()
                    continue
                
                # Watch video
                self._watch_video()
                self.stats.videos_watched += 1
                self._send_stats_update()
                
                # Decide and execute actions
                self._decide_and_execute_actions(video_info)
                
                # Check if pause needed
                self._check_pause_needed()
                
                # Scroll to next video
                self._scroll_to_next()
            
            self.logger.info(f"✅ Search workflow completed: {self.stats.videos_watched} videos watched")
            
        except Exception as e:
            self.logger.error(f"❌ Error in Search workflow: {e}")
            self.stats.errors += 1
        
        return self.stats
    
    def _navigate_to_search_videos(self) -> bool:
        """Navigate to search and open first video."""
        self.logger.info(f"🔍 Navigating to search: {self.config.search_query}")
        
        return self.navigation.search_and_open_videos(self.config.search_query)
    
    def _scroll_to_next(self):
        """Scroll to next video."""
        self.scroll.scroll_to_next_video()
        time.sleep(0.5)
    
    def _watch_video(self):
        """Watch current video for a random duration."""
        watch_time = random.uniform(
            self.config.min_watch_time,
            self.config.max_watch_time
        )
        self.logger.debug(f"👀 Watching video for {watch_time:.1f}s")
        time.sleep(watch_time)
    
    def _should_skip_video(self, video_info: Dict[str, Any]) -> bool:
        """Check if video should be skipped based on filters."""
        # Skip if already liked
        if self.config.skip_already_liked and video_info.get('is_liked'):
            return True
        
        # Check like count filters
        like_count = self._parse_count(video_info.get('like_count', '0'))
        
        if self.config.min_likes and like_count < self.config.min_likes:
            return True
        
        if self.config.max_likes and like_count > self.config.max_likes:
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
            self._send_stats_update()
            
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
            self._send_stats_update()
            
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
            self._send_stats_update()
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
            
            if self._on_pause_callback:
                try:
                    self._on_pause_callback(pause_seconds)
                except Exception as e:
                    self.logger.warning(f"Error sending pause callback: {e}")
            
            time.sleep(pause_duration)
            self._actions_since_pause = 0
    
    def _handle_popups(self):
        """Check for and close any popups."""
        # First check for Android system popups (input method selection, etc.)
        if self.click.close_system_popup():
            self.stats.popups_closed += 1
            self.logger.info("✅ System popup closed")
            time.sleep(0.5)
            return
        
        # Check for notification banner (e.g., "X sent you new messages")
        if self.click.dismiss_notification_banner():
            self.stats.popups_closed += 1
            self.logger.info("✅ Notification banner dismissed")
            time.sleep(0.5)
            return
        
        # Check if accidentally on Inbox page
        if self.detection.is_on_inbox_page():
            self.click.escape_inbox_page()
            self.stats.popups_closed += 1
            self.logger.info("✅ Escaped from Inbox page")
            time.sleep(0.5)
            return
        
        # Check for "Link email" popup
        if self.detection.has_link_email_popup():
            if self.click.close_link_email_popup():
                self.stats.popups_closed += 1
                self.logger.info("✅ 'Link email' popup closed")
                time.sleep(0.5)
                return
        
        if self.detection.has_popup():
            self.logger.info("🚨 Popup detected, attempting to close")
            
            # Try to close "Follow your friends" popup
            if self.detection.has_follow_friends_popup():
                if self.click.close_follow_friends_popup():
                    self.stats.popups_closed += 1
                    self.logger.info("✅ 'Follow your friends' popup closed")
                    time.sleep(0.5)
                    return
            
            # Try to close collections popup
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
                return int(count_str.replace(',', '').replace('.', ''))
        except (ValueError, AttributeError):
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current workflow statistics."""
        return self.stats.to_dict()
