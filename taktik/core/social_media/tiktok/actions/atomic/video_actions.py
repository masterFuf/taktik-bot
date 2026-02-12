"""Atomic video interaction actions for TikTok.

Extracted from click_actions.py — contains only video-specific actions
(like, comment, share, favorite, sound, creator profile, follow on video).

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.
"""

from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import VIDEO_SELECTORS


class VideoActions(BaseAction):
    """Low-level click actions for TikTok video UI elements."""
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-video-atomic")
        self.video_selectors = VIDEO_SELECTORS
    
    def click_like_button(self) -> bool:
        """Click Like button on video.
        
        Uses resource-id f57 with content-desc "Like video".
        """
        self.logger.debug("❤️ Clicking Like button")
        return self._find_and_click(self.video_selectors.like_button, timeout=3)
    
    def double_tap_like(self) -> bool:
        """Double tap to like video (TikTok specific).
        
        Taps on the video container (gy_ or long_press_layout).
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
        
        Uses resource-id dtv with content-desc "Read or add comments".
        """
        self.logger.debug("💬 Clicking Comment button")
        return self._find_and_click(self.video_selectors.comment_button, timeout=5)
    
    def click_share_button(self) -> bool:
        """Click Share button on video.
        
        Uses resource-id f57 with content-desc "Share video".
        """
        self.logger.debug("🔗 Clicking Share button")
        return self._find_and_click(self.video_selectors.share_button, timeout=5)
    
    def click_favorite_button(self) -> bool:
        """Click Favorite button on video.
        
        Uses resource-id guh with content-desc "Add or remove this video from Favourites".
        """
        self.logger.debug("⭐ Clicking Favorite button")
        return self._find_and_click(self.video_selectors.favorite_button, timeout=5)
    
    def click_sound_button(self) -> bool:
        """Click Sound button on video (rotating disc).
        
        Uses resource-id nhe with content-desc "Sound: {sound_name}".
        """
        self.logger.debug("🎵 Clicking Sound button")
        return self._find_and_click(self.video_selectors.sound_button, timeout=5)
    
    def click_creator_profile(self) -> bool:
        """Click on creator's profile image on video.
        
        Uses resource-id yx4 with content-desc "{username} profile".
        """
        self.logger.debug("👤 Clicking Creator profile")
        return self._find_and_click(self.video_selectors.creator_profile_image, timeout=5)
    
    def click_video_follow_button(self) -> bool:
        """Click Follow button on video (under creator profile).
        
        Uses resource-id hi1 with content-desc "Follow {username}".
        """
        self.logger.debug("👤 Clicking Follow button on video")
        return self._find_and_click(self.video_selectors.follow_button, timeout=5)
    
    def like_video(self) -> bool:
        """Like current video (try button first, then double tap)."""
        try:
            self.logger.info("❤️ Attempting to like video")
            
            # Try clicking like button first
            if self.click_like_button():
                self.logger.success("✅ Video liked via button")
                return True
            
            # Fallback: double tap
            if self.double_tap_like():
                self.logger.success("✅ Video liked via double tap")
                return True
            
            self.logger.warning("❌ Failed to like video")
            return False
            
        except Exception as e:
            self.logger.error(f"Error liking video: {e}")
            return False
