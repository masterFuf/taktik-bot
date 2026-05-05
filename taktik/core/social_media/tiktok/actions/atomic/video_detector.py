"""Atomic video state detection for TikTok.

Extracted from detection_actions.py — contains video-specific detection:
like/favorite/follow state, video info extraction, ad detection, profile info.

Dernière mise à jour: mai 2026
Basé sur les UI dumps réels de TikTok.
Compatible v35 (IDs: f57, hi1, f4z text nodes) et v40+ (IDs: fia, i0z, counts in content-desc).
"""

import re
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
        return self._element_exists(self.video_selectors.unlike_indicator, timeout=1)

    def is_video_favorited(self) -> bool:
        return self._element_exists(self.video_selectors.video_favorited_indicator, timeout=1)

    def is_user_followed(self) -> bool:
        return self._element_exists(self.video_selectors.user_followed_indicator, timeout=1)

    # === Video Info Extraction ===

    def get_video_author(self) -> Optional[str]:
        """Get current video author username.
        
        v35: resource-id/title[@text="username"]
        v40+: resource-id/user_avatar[@content-desc="username profile"]
              or resource-id/i0z[@content-desc="Follow username"]
        """
        # Try text= first (v35)
        text = self._get_element_text(self.video_selectors.author_username, timeout=1)
        if text:
            return text

        # v40+: parse from user_avatar content-desc ("username profile")
        desc = self._get_element_content_desc(
            ['//*[@resource-id="com.zhiliaoapp.musically:id/user_avatar"]'], timeout=1
        )
        if desc and desc.endswith(' profile'):
            return desc[: -len(' profile')].strip()

        # Fallback: parse from Follow button content-desc ("Follow username")
        desc = self._get_element_content_desc(
            ['//*[@resource-id="com.zhiliaoapp.musically:id/i0z"]'], timeout=1
        )
        if desc and desc.startswith('Follow '):
            return desc[len('Follow '):].strip()

        return None

    def get_video_description(self) -> Optional[str]:
        return self._get_element_text(self.video_selectors.video_description, timeout=1)

    def get_video_like_count(self) -> Optional[str]:
        """Get like count.
        
        v35: resource-id/f4z[@text="4385"]
        v40+: resource-id/fia[@content-desc="Like video 4,385 likes"]
        """
        # Try text= first (v35)
        count = self._get_element_text(self.video_selectors.like_count, timeout=1)
        if count:
            return count

        # v40+: parse from like button content-desc
        desc = self._get_element_content_desc(
            self.video_selectors.like_button_for_count, timeout=1
        )
        if desc:
            # "Like video 4,385 likes" → "4,385"
            m = re.search(r'Like video (.+?) like', desc)
            if m:
                return m.group(1).strip()

        return None

    def get_video_comment_count(self) -> Optional[str]:
        """Get comment count.
        
        v35: resource-id/dp9[@text="42"]
        v40+: resource-id/e4q[@content-desc="Read or add comments. 42 comments"]
        """
        # Try text= first (v35)
        count = self._get_element_text(self.video_selectors.comment_count, timeout=1)
        if count:
            return count

        # v40+: parse from comment button content-desc
        desc = self._get_element_content_desc(
            self.video_selectors.comment_button_for_count, timeout=1
        )
        if desc:
            # "Read or add comments. 42 comments" → "42"
            m = re.search(r'(\d[\d,\.]*)\s+comment', desc)
            if m:
                return m.group(1).strip()

        return None

    def get_video_info(self, include_comment_count: bool = False) -> Dict[str, Any]:
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
        
        Détecte via le label "Ad" (TextView text="Ad") visible sur les vidéos sponsorisées.
        Note: ru3 est un FrameLayout présent sur toutes les vidéos — on filtre sur @text="Ad".
        """
        return self._element_exists(self.video_selectors.ad_label, timeout=1)
