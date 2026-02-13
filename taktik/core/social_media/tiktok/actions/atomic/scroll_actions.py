"""Atomic scroll actions for TikTok.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.
"""

from loguru import logger
import time
import random

from ..core.base_action import BaseAction
from ...ui.selectors import VIDEO_SELECTORS, SCROLL_SELECTORS


class ScrollActions(BaseAction):
    """Low-level scroll actions for TikTok.
    
    Actions de scroll spécifiques à TikTok (vidéos verticales).
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-scroll-atomic")
        self.video_selectors = VIDEO_SELECTORS
        self.scroll_selectors = SCROLL_SELECTORS
    
    def scroll_to_next_video(self) -> bool:
        """Scroll to next video in feed."""
        try:
            self.logger.debug("📱 Scrolling to next video")
            self._swipe_to_next_video()
            
            # Wait for video to load
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling to next video: {e}")
            return False
    
    def scroll_profile_videos(self, direction: str = 'down') -> bool:
        """Scroll through videos on profile page."""
        try:
            self.logger.debug(f"📱 Scrolling profile videos {direction}")
            
            if direction.lower() == 'down':
                self._scroll_down()
            else:
                self._scroll_up()
            
            time.sleep(0.3)
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling profile videos: {e}")
            return False
    
    def scroll_search_results(self, direction: str = 'down') -> bool:
        """Scroll through search results."""
        try:
            self.logger.debug(f"📱 Scrolling search results {direction}")
            
            if direction.lower() == 'down':
                self._scroll_down()
            else:
                self._scroll_up()
            
            time.sleep(0.3)
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling search results: {e}")
            return False
    
    def is_loading(self) -> bool:
        """Check if content is loading."""
        return self._element_exists(self.scroll_selectors.loading_indicator, timeout=1)
    
    def watch_video(self, duration: float = 3.0) -> bool:
        """Watch current video for specified duration."""
        try:
            self.logger.debug(f"👀 Watching video for {duration}s")
            
            # Random variation in watch time
            actual_duration = duration + random.uniform(-0.5, 1.0)
            actual_duration = max(1.0, actual_duration)
            
            time.sleep(actual_duration)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error watching video: {e}")
            return False
    
