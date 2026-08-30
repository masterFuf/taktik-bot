"""Atomic video interaction actions for TikTok.

Extracted from click_actions.py — contains only video-specific actions
(like, comment, share, favorite, sound, creator profile, follow on video).

"""

from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors.surfaces.video import VIDEO_SELECTORS


class VideoActions(BaseAction):
    """Low-level click actions for TikTok video UI elements."""
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-video-atomic")
        self.video_selectors = VIDEO_SELECTORS
    
    def click_like_button(self) -> bool:
        """Click Like button on video.
        
        Uses the stable like rail structure (`f57` + child `f4u`) with
        localized FR/EN content-desc fallbacks.
        """
        self.logger.debug("❤️ Clicking Like button")
        return self._find_and_click(self.video_selectors.like_button, timeout=3)
    
    def double_tap_like(self) -> bool:
        """Double tap to like video (TikTok specific).

        Taps on the video container (gy_ or long_press_layout).

        DOES NOT LIKE ANYTHING. Measured on 46.6.3 on 2026-08-30, on a video confirmed to carry an
        unliked heart rail, with four different ways of delivering the gesture: uiautomator2's
        `double_click` at its default gap and at 50 ms, two `input tap` chained in one shell, and
        two `click` calls back to back. Neither probe moved -- the heart kept its `J'aime`
        content-desc and the like counter kept its value.

        Which is worth knowing before reaching for this. Double-tapping the video is the canonical
        human way to like on TikTok, so varying the like gesture between it and the heart rail is
        the obvious humanisation win -- and it is not available to us. A coin flip that picks this
        half the time would spend two taps and a screen read, then fall back to the heart, every
        single time. The gesture is presumably filtered or needs a real touch stream our injection
        path cannot produce, which is the same wall as the 8-16 Hz injection cadence.

        Kept rather than deleted because the Lab exercises it and because a measured negative is
        worth more than an absence -- but a caller wanting a like should use
        `click_like_button()`.
        """
        self.logger.debug("❤️ Double tapping to like")
        try:
            self._double_tap_to_like()
            return True
        except Exception as e:
            self.logger.error(f"Error double tapping: {e}")
            return False
    
    def click_comment_button(self) -> bool:
        """Click Comment button on video.
        
        Uses resource-id `dtv` with localized FR/EN content-desc fallbacks.
        """
        self.logger.debug("💬 Clicking Comment button")
        return self._find_and_click(self.video_selectors.comment_button, timeout=5)
    
    def click_share_button(self) -> bool:
        """Click Share button on video.
        
        Uses the stable share rail structure (`f57` + child `t_j`) with
        localized FR/EN content-desc fallbacks.
        """
        self.logger.debug("🔗 Clicking Share button")
        return self._find_and_click(self.video_selectors.share_button, timeout=5)
    
    def click_favorite_button(self) -> bool:
        """Click Favorite button on video.
        
        Uses resource-id `guh` with localized FR/EN content-desc fallbacks.
        """
        self.logger.debug("⭐ Clicking Favorite button")
        return self._find_and_click(self.video_selectors.favorite_button, timeout=5)
    
    def click_video_follow_button(self) -> bool:
        """Click Follow button on video (under creator profile).
        
        Uses resource-id `hi1` with localized FR/EN content-desc fallbacks.
        """
        self.logger.debug("👤 Clicking Follow button on video")
        return self._find_and_click(self.video_selectors.follow_button, timeout=5)
    
