"""Atomic video state detection for TikTok.

Extracted from detection_actions.py — contains video-specific detection:
like/favorite/follow state, video info extraction, ad detection, profile info.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.
"""

from typing import Optional, Dict, Any
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import VIDEO_SELECTORS


class VideoDetector(BaseAction):
    """Detects video and profile state on TikTok UI."""

    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-video-detector")
        self.video_selectors = VIDEO_SELECTORS

    # === Video State Detection ===

    def is_video_liked(self) -> bool:
        """Check if current video is liked.
        
        Détecte via le content-desc qui change de "Like" à "Unlike".
        """
        return self._element_exists(self.video_selectors.unlike_indicator, timeout=1)

    def is_video_favorited(self) -> bool:
        """Check if current video is in favorites."""
        return self._element_exists(self.video_selectors.video_favorited_indicator, timeout=1)

    def is_user_followed(self) -> bool:
        """Check if current user is followed.
        
        Détecte via le texte du bouton qui change de "Follow" à "Following" ou "Friends".
        """
        return self._element_exists(self.video_selectors.user_followed_indicator, timeout=1)

    # === Video Info Extraction ===

    def get_video_author(self) -> Optional[str]:
        """Get current video author username."""
        return self._get_element_text(self.video_selectors.author_username, timeout=1)

    def get_video_description(self) -> Optional[str]:
        """Get current video description."""
        return self._get_element_text(self.video_selectors.video_description, timeout=1)

    def get_video_like_count(self) -> Optional[str]:
        """Get current video like count."""
        return self._get_element_text(self.video_selectors.like_count, timeout=1)

    def get_video_comment_count(self) -> Optional[str]:
        """Get current video comment count."""
        return self._get_element_text(self.video_selectors.comment_count, timeout=1)

    def get_video_info(self, include_comment_count: bool = False) -> Dict[str, Any]:
        """Get all available info about current video.
        
        Args:
            include_comment_count: If True, also fetch comment count (slower).
        """
        info = {
            'author': self.get_video_author(),
            'description': self.get_video_description(),
            'like_count': self.get_video_like_count(),
            'is_liked': self.is_video_liked(),
            'is_favorited': self.is_video_favorited(),
            'is_ad': self.is_ad_video(),
        }
        if include_comment_count:
            info['comment_count'] = self.get_video_comment_count()
        return info

    # === Ad Detection ===

    def is_ad_video(self) -> bool:
        """Check if current video is an advertisement.
        
        Détecte via le label "Ad" visible sur les vidéos sponsorisées.
        Resource-id: com.zhiliaoapp.musically:id/ru3
        """
        return self._element_exists(self.video_selectors.ad_label, timeout=1)
