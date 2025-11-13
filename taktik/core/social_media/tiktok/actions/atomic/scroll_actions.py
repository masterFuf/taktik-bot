"""Atomic scroll actions for TikTok."""

from typing import Optional, Dict, Any
from loguru import logger
import time

from ..core.base_action import BaseAction
from ...ui.selectors import VIDEO_SELECTORS, SCROLL_SELECTORS


class ScrollActions(BaseAction):
    """Low-level scroll actions for TikTok."""
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-scroll-atomic")
    
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
    
    def scroll_to_previous_video(self) -> bool:
        """Scroll to previous video in feed."""
        try:
            self.logger.debug("📱 Scrolling to previous video")
            self._swipe_to_previous_video()
            
            # Wait for video to load
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling to previous video: {e}")
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
    
    def scroll_comments(self, direction: str = 'down') -> bool:
        """Scroll through comments."""
        try:
            self.logger.debug(f"📱 Scrolling comments {direction}")
            
            if direction.lower() == 'down':
                self._scroll_down(scale=0.6)
            else:
                self._scroll_up(scale=0.6)
            
            time.sleep(0.3)
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling comments: {e}")
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
        return self._element_exists(SCROLL_SELECTORS.loading_indicator, timeout=1)
    
    def wait_for_loading_complete(self, timeout: float = 10.0) -> bool:
        """Wait for loading to complete."""
        self.logger.debug("⏳ Waiting for loading to complete")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if not self.is_loading():
                self.logger.debug("✅ Loading complete")
                return True
            
            time.sleep(0.5)
        
        self.logger.warning("⏳ Loading timeout")
        return False
    
    def is_end_of_list(self) -> bool:
        """Check if reached end of list/feed."""
        return self._element_exists(SCROLL_SELECTORS.end_of_list, timeout=1)
    
    def watch_video(self, duration: float = 3.0) -> bool:
        """Watch current video for specified duration."""
        try:
            self.logger.debug(f"👀 Watching video for {duration}s")
            
            # Random variation in watch time
            import random
            actual_duration = duration + random.uniform(-0.5, 1.0)
            actual_duration = max(1.0, actual_duration)
            
            time.sleep(actual_duration)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error watching video: {e}")
            return False
    
    def scroll_through_videos(self, count: int = 5, watch_duration: float = 3.0) -> int:
        """Scroll through multiple videos, watching each one."""
        self.logger.info(f"📱 Scrolling through {count} videos")
        
        scrolled = 0
        
        for i in range(count):
            try:
                # Watch current video
                self.watch_video(watch_duration)
                
                # Scroll to next
                if self.scroll_to_next_video():
                    scrolled += 1
                    self.logger.debug(f"✅ Scrolled to video {i+1}/{count}")
                else:
                    self.logger.warning(f"❌ Failed to scroll to video {i+1}/{count}")
                    break
                
                # Check if end of feed
                if self.is_end_of_list():
                    self.logger.info("📱 Reached end of feed")
                    break
                
            except Exception as e:
                self.logger.error(f"Error at video {i+1}: {e}")
                break
        
        self.logger.info(f"✅ Scrolled through {scrolled}/{count} videos")
        return scrolled
