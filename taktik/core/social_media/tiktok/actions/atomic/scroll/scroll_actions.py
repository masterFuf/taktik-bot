"""Atomic scroll actions for TikTok.

"""

from loguru import logger
import time
import random

from ...core.base_action import BaseAction
from ....ui.selectors.support.scroll import SCROLL_SELECTORS
from ....ui.selectors.surfaces.video import VIDEO_SELECTORS


class ScrollActions(BaseAction):
    """Low-level scroll actions for TikTok.
    
    Actions de scroll spécifiques à TikTok (vidéos verticales).
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-scroll-atomic")
        self.video_selectors = VIDEO_SELECTORS
        self.scroll_selectors = SCROLL_SELECTORS
    
    def _current_video_signature(self):
        """Read the visible video's stable identity in one hierarchy snapshot."""
        try:
            snapshot = self.device.read_video_snapshot()
            # The following metadata read consumes this result, so transition verification and
            # extraction observe the same frame without paying for two dumps.
            self.device.remember_video_snapshot(snapshot)
            return snapshot.signature if snapshot.video_visible else None
        except Exception as exc:
            self.logger.debug(f"Could not verify video transition: {exc}")
            return None

    def scroll_to_next_video(self, previous_signature=None) -> bool:
        """Scroll one video and retry once when the pager did not advance.

        Callers without a signature retain the historical fire-and-settle behavior. Feed callers
        pass the snapshot identity they already own, allowing this action to distinguish a gesture
        that executed from a pager transition that actually succeeded.
        """
        try:
            attempts = 2 if previous_signature else 1
            for attempt in range(attempts):
                self.logger.debug("📱 Scrolling to next video")
                self._swipe_to_next_video()

                if not previous_signature:
                    time.sleep(0.5)
                    return True

                # The gesture primitive already includes its touch-release delay. A short settle
                # lets the pager commit; the hierarchy read itself synchronizes with the slower
                # Galaxy A11 accessibility service.
                time.sleep(0.2)
                current_signature = self._current_video_signature()
                if current_signature is None:
                    # Observation failed, not the gesture. Preserve the old success semantics so
                    # a temporary dump failure does not turn normal scrolling into an error loop.
                    return True
                if current_signature != previous_signature:
                    return True
                if attempt == 0:
                    self.logger.warning("⚠️ Feed swipe left the same video visible; retrying safely")

            self.logger.warning("❌ Feed stayed on the same video after the retry")
            return False
            
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
    
