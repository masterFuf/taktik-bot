"""Atomic video state detection for TikTok.

Extracted from detection_actions.py — contains video-specific detection:
like/favorite/follow state, video info extraction, ad detection, profile info.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.
"""

import re
from typing import Optional, Dict, Any
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import VIDEO_SELECTORS

# Selectors for trill/musically author avatar (content-desc = "username profile")
_AUTHOR_CONTENT_DESC_SELECTORS = [
    '//*[@resource-id="com.ss.android.ugc.trill:id/yx4"]',
    '//*[@resource-id="com.zhiliaoapp.musically:id/yx4"]',
]

# Selectors for like button with count in content-desc (e.g. "Like video. 2 likes")
_LIKE_CONTENT_DESC_SELECTORS = [
    '//*[@resource-id="com.ss.android.ugc.trill:id/f57"][contains(@content-desc, "Like video")]',
    '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Like video")]',
    '//*[contains(@content-desc, "Like video")]',
]

# Selectors for comment button with count in content-desc
_COMMENT_CONTENT_DESC_SELECTORS = [
    '//*[@resource-id="com.ss.android.ugc.trill:id/dtv"]',
    '//*[@resource-id="com.zhiliaoapp.musically:id/dtv"]',
    '//*[contains(@content-desc, "comments")]',
]


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
        """Get current video author username.
        
        Tries text node first (musically), then parses content-desc of the
        author avatar element (trill: content-desc = "username profile").
        """
        # Try text node (older/musically variant)
        text = self._get_element_text(self.video_selectors.author_username, timeout=1)
        if text:
            return text

        # Trill variant: avatar content-desc = "some username profile"
        desc = self._get_element_content_desc(_AUTHOR_CONTENT_DESC_SELECTORS, timeout=1)
        if desc and desc.endswith(' profile'):
            return desc[:-len(' profile')].strip()

        return None

    def get_video_description(self) -> Optional[str]:
        """Get current video description."""
        return self._get_element_text(self.video_selectors.video_description, timeout=1)

    def get_video_like_count(self) -> Optional[str]:
        """Get current video like count.
        
        Tries text node first (musically), then parses content-desc
        (trill: "Like video. 2 likes" or "Like video. 1.2K likes").
        """
        # Try text node (older/musically variant)
        count = self._get_element_text(self.video_selectors.like_count, timeout=1)
        if count:
            return count

        # Trill variant: "Like video. 2 likes" / "Like video. 1.2K likes"
        desc = self._get_element_content_desc(_LIKE_CONTENT_DESC_SELECTORS, timeout=1)
        if desc:
            m = re.search(r'Like video[.\s]+(.+?)\s+like', desc, re.IGNORECASE)
            if m:
                return m.group(1).strip()

        return None

    def get_video_comment_count(self) -> Optional[str]:
        """Get current video comment count.
        
        Trill: content-desc = "Read or add comments. 0 comments".
        """
        count = self._get_element_text(self.video_selectors.comment_count, timeout=1)
        if count:
            return count

        desc = self._get_element_content_desc(_COMMENT_CONTENT_DESC_SELECTORS, timeout=1)
        if desc:
            m = re.search(r'comments?\.\s+(.+?)\s+comment', desc, re.IGNORECASE)
            if m:
                return m.group(1).strip()

        return None

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
