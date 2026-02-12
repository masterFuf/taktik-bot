"""Atomic video state detection for TikTok.

Extracted from detection_actions.py — contains video-specific detection:
like/favorite/follow state, video info extraction, ad detection, profile info.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.
"""

from typing import Optional, Dict, Any
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import VIDEO_SELECTORS, PROFILE_SELECTORS


class VideoDetector(BaseAction):
    """Detects video and profile state on TikTok UI."""

    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-video-detector")
        self.video_selectors = VIDEO_SELECTORS
        self.profile_selectors = PROFILE_SELECTORS

    # === Video State Detection ===

    def is_video_liked(self) -> bool:
        """Check if current video is liked.
        
        Détecte via le content-desc qui change de "Like" à "Unlike".
        """
        unlike_indicators = [
            '//*[contains(@content-desc, "Unlike")]',
            '//*[contains(@content-desc, "Liked")]',
            '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Unlike")]',
        ]
        return self._element_exists(unlike_indicators, timeout=1)

    def is_video_favorited(self) -> bool:
        """Check if current video is in favorites."""
        favorited_indicators = [
            '//*[contains(@content-desc, "Remove from Favourites")]',
            '//*[contains(@content-desc, "Retirer des favoris")]',
        ]
        return self._element_exists(favorited_indicators, timeout=1)

    def is_user_followed(self) -> bool:
        """Check if current user is followed.
        
        Détecte via le texte du bouton qui change de "Follow" à "Following" ou "Friends".
        """
        following_indicators = [
            '//android.widget.Button[@text="Following"]',
            '//android.widget.Button[@text="Abonné"]',
            '//android.widget.Button[contains(@text, "Friends")]',
            '//*[contains(@content-desc, "Unfollow")]',
        ]
        return self._element_exists(following_indicators, timeout=1)

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

    # === Profile Info Extraction ===

    def get_profile_display_name(self) -> Optional[str]:
        """Get profile display name."""
        return self._get_element_text(self.profile_selectors.display_name, timeout=2)

    def get_profile_username(self) -> Optional[str]:
        """Get profile @username."""
        return self._get_element_text(self.profile_selectors.username, timeout=2)

    def get_profile_stats(self) -> Dict[str, Optional[str]]:
        """Get profile statistics (following, followers, likes)."""
        stat_values = []

        for i in range(3):
            selector = f'(//*[@resource-id="com.zhiliaoapp.musically:id/qfw"])[{i+1}]'
            value = self._get_element_text([selector], timeout=1)
            stat_values.append(value)

        return {
            'following': stat_values[0] if len(stat_values) > 0 else None,
            'followers': stat_values[1] if len(stat_values) > 1 else None,
            'likes': stat_values[2] if len(stat_values) > 2 else None,
        }

    def get_profile_info(self) -> Dict[str, Any]:
        """Get all available info about current profile."""
        stats = self.get_profile_stats()
        return {
            'display_name': self.get_profile_display_name(),
            'username': self.get_profile_username(),
            'following': stats.get('following'),
            'followers': stats.get('followers'),
            'likes': stats.get('likes'),
            'is_followed': self.is_user_followed(),
        }
