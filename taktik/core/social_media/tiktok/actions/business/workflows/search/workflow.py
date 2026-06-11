"""Search/Target Workflow for TikTok automation.

Dernière mise à jour: 11 janvier 2026
Basé sur les UI dumps réels de TikTok.

Ce workflow permet d'automatiser les interactions sur les vidéos trouvées via recherche:
- Rechercher un terme (hashtag, username, keyword)
- Cliquer sur l'onglet Videos
- Ouvrir la première vidéo
- Scroller et interagir avec les vidéos (like, follow, favorite)
"""

from typing import Optional, Dict, Any
import time
import random

from taktik.core.shared.telemetry.sink import emit_step

from .._internal import BaseVideoWorkflow, VideoWorkflowStats
from .models import SearchConfig


# Backward-compat alias
SearchStats = VideoWorkflowStats


class SearchWorkflow(BaseVideoWorkflow):
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
        super().__init__(device, module_name="tiktok-search-workflow")
        self.config = config or SearchConfig()
        self.stats = VideoWorkflowStats()
    
    def run(self) -> VideoWorkflowStats:
        """Run the Search workflow.
        
        Returns:
            VideoWorkflowStats: Statistics from the workflow run
        """
        if not self.config.search_query:
            self.logger.error("❌ No search query provided")
            return self.stats
        
        self.logger.info(f"🚀 Starting Search workflow for: {self.config.search_query}")
        self.logger.info(f"📊 Config: max_videos={self.config.max_videos}, "
                        f"like_prob={self.config.like_probability}, "
                        f"follow_prob={self.config.follow_probability}")
        
        self._running = True
        self.stats = VideoWorkflowStats()
        
        try:
            # Navigate to search and open videos
            if not self._navigate_to_search_videos():
                self.logger.error("❌ Failed to navigate to search videos")
                return self.stats
            
            # Process videos
            while self._running and self.stats.videos_watched < self.config.max_videos:
                if not self._wait_if_paused():
                    break
                
                # Check and close any popups first
                self._handle_popups()
                
                # Check limits
                if self._check_limits_reached():
                    self.logger.info("📊 Session limits reached")
                    break
                
                # Get video info
                video_info = self.detection.get_video_info()
                
                # Detect stuck state
                if self._handle_stuck_video(video_info):
                    continue
                
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
                
                # Watch + decide. Heartbeat: attribute the per-video processing time
                # (watch + decide + act) in the cadence/run log.
                _liked0 = getattr(self.stats, 'videos_liked', 0)
                _follow0 = getattr(self.stats, 'users_followed', 0)
                _fav0 = getattr(self.stats, 'videos_favorited', 0)
                _t0 = time.time()
                emit_step("analysis", action="start", target="search")
                self._watch_video()
                self.stats.videos_watched += 1
                self._send_stats_update()
                self._decide_and_execute_actions(video_info)
                _acted = (getattr(self.stats, 'videos_liked', 0) > _liked0
                          or getattr(self.stats, 'users_followed', 0) > _follow0
                          or getattr(self.stats, 'videos_favorited', 0) > _fav0)
                emit_step("analysis", action="done",
                          duration_ms=int((time.time() - _t0) * 1000),
                          outcome="interacted" if _acted else "watched")

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
