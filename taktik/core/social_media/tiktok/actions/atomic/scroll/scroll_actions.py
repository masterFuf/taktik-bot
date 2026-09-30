"""Atomic scroll actions for TikTok.

"""

from loguru import logger
import time
import random

from taktik.core.shared.behavior.sampling import sample_within

from taktik.core.social_media.tiktok.actions.core.base_action import BaseAction
from taktik.core.social_media.tiktok.actions.atomic.detection.screen_reading import read_until
from taktik.core.social_media.tiktok.ui.selectors.support.scroll import SCROLL_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import VIDEO_SELECTORS


class ScrollActions(BaseAction):
    """Low-level scroll actions for TikTok.
    
    Actions de scroll spécifiques à TikTok (vidéos verticales).
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-scroll-atomic")
        self.video_selectors = VIDEO_SELECTORS
        self.scroll_selectors = SCROLL_SELECTORS
    
    #: Swipes spent on one advance: the pager that snapped back is swiped once more.
    NEXT_VIDEO_ATTEMPTS = 2

    def scroll_to_next_video(self) -> bool:
        """Scroll to the next video and read the screen again to check that the video changed.

        The feed pager snaps back when a drag stops short (under ~0.4 of the screen on a Pixel 6a,
        TikTok 47.0.3), and this used to answer True whatever happened. The video is told apart
        by `VideoDetector.video_identity`, the fields the stuck-video check compares. False when
        the same video is still there after `NEXT_VIDEO_ATTEMPTS` swipes.
        """
        try:
            self.logger.debug("📱 Scrolling to next video")
            before = self._read_video_identity()
            for attempt in range(1, self.NEXT_VIDEO_ATTEMPTS + 1):
                self._swipe_to_next_video()
                if before is None:
                    # Nothing to compare with (no author, count or caption on the photo).
                    self.logger.debug("next video not verified: no video identity before the swipe")
                    time.sleep(0.5)
                    return True
                after = self._read_video_identity(until=lambda identity: identity != before)
                if after != before:
                    return True
                self.logger.warning(f"same video after swipe {attempt}: the pager snapped back")
            return False

        except Exception as e:
            self.logger.error(f"Error scrolling to next video: {e}")
            return False

    def _video_detector(self):
        detector = self.__dict__.get("_detector")
        if detector is None:
            from taktik.core.social_media.tiktok.actions.atomic.detection.video_detector import VideoDetector
            detector = self.__dict__["_detector"] = VideoDetector(self.device)
        return detector

    def _read_video_identity(self, until=None):
        """The identity of the video on screen, on new photos until `until(identity)` holds
        (2 s at most); the first photo read when no condition is given."""
        return read_until(self.device, self._video_detector().video_identity,
                          until or (lambda _identity: True))
    
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
            
            # Random variation in watch time, never under a second (drawn again, not floored)
            actual_duration = sample_within(lambda: duration + random.uniform(-0.5, 1.0),
                                            1.0, float('inf'), edge_band=0.5)
            
            time.sleep(actual_duration)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error watching video: {e}")
            return False
    
