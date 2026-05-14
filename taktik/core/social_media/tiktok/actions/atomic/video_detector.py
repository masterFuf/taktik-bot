"""Atomic video state detection for TikTok.

Extracted from detection_actions.py — contains video-specific detection:
like/favorite/follow state, video info extraction, ad detection, profile info.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.
"""

import re
from typing import Optional, Dict, Any, List
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import VIDEO_SELECTORS

# TikTok packages (resource IDs identical across variants)
_TIKTOK_PACKAGES = [
    'com.ss.android.ugc.trill',
    'com.zhiliaoapp.musically',
    'com.ss.android.ugc.aweme',
]

# Selectors for trill/musically author avatar (content-desc = "username profile")
_AUTHOR_CONTENT_DESC_SELECTORS = [
    f'//*[@resource-id="{p}:id/yx4"]' for p in _TIKTOK_PACKAGES
]

# Selectors for like button with count in content-desc (e.g. "Like video. 2 likes")
_LIKE_CONTENT_DESC_SELECTORS = [
    *[f'//*[@resource-id="{p}:id/f57"][contains(@content-desc, "Like video")]' for p in _TIKTOK_PACKAGES],
    '//*[contains(@content-desc, "Like video")]',
]

# Selectors for comment button with count in content-desc
_COMMENT_CONTENT_DESC_SELECTORS = [
    *[f'//*[@resource-id="{p}:id/dtv"]' for p in _TIKTOK_PACKAGES],
    '//*[contains(@content-desc, "comments")]',
]

# Selectors for description element (video caption)
_DESC_SELECTORS = [f'//*[@resource-id="{p}:id/desc"]' for p in _TIKTOK_PACKAGES]

# Selectors for sound/music button
_SOUND_SELECTORS = [
    *[f'//*[@resource-id="{p}:id/nhe"]' for p in _TIKTOK_PACKAGES],
    '//android.widget.Button[contains(@content-desc, "Sound:")]',
]


def _parse_description(raw: str) -> Dict[str, Any]:
    """Split raw description text into clean text and hashtag list."""
    # Extract all hashtags
    hashtags: List[str] = re.findall(r'#\w+', raw)
    # Remove hashtags and trailing truncation markers
    clean = re.sub(r'#\w+', '', raw)
    clean = re.sub(r'[…\.]{1,3}more\s*$', '', clean, flags=re.IGNORECASE).strip()
    return {
        'description_text': clean if clean else None,
        'hashtags': hashtags,
    }


class VideoDetector(BaseAction):
    """Detects video and profile state on TikTok UI."""

    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-video-detector")
        self.video_selectors = VIDEO_SELECTORS

    # === Video State Detection ===

    def is_video_liked(self) -> bool:
        """Check if current video is liked."""
        return self._element_exists(self.video_selectors.unlike_indicator, timeout=1)

    def is_video_favorited(self) -> bool:
        """Check if current video is in favorites."""
        return self._element_exists(self.video_selectors.video_favorited_indicator, timeout=1)

    def is_user_followed(self) -> bool:
        """Check if current user is followed."""
        return self._element_exists(self.video_selectors.user_followed_indicator, timeout=1)

    # === Video Info Extraction ===

    def get_video_author(self) -> Optional[str]:
        """Get current video author username.

        Tries text node first (musically), then parses content-desc of the
        author avatar element (trill: content-desc = "username profile").
        """
        text = self._get_element_text(self.video_selectors.author_username, timeout=1)
        if text:
            return text

        desc = self._get_element_content_desc(_AUTHOR_CONTENT_DESC_SELECTORS, timeout=1)
        if desc and desc.endswith(' profile'):
            return desc[:-len(' profile')].strip()

        return None

    def get_video_description(self) -> Optional[str]:
        """Get raw description text (may be truncated with '…more')."""
        return self._get_element_text(self.video_selectors.video_description, timeout=1)

    def get_video_description_full(self) -> Optional[str]:
        """Get the complete video description, expanding '…more' if present.

        Clicks the description element to expand it when truncated, then
        re-reads the full text.  Returns the raw (unparsed) full string.
        """
        raw = self._get_element_text(self.video_selectors.video_description, timeout=1)
        if not raw:
            return None

        # Check if truncated
        if 'more' in raw and ('…' in raw or raw.rstrip().endswith('...more')):
            try:
                for sel in _DESC_SELECTORS:
                    elem = self.device.xpath(sel)
                    if elem.exists:
                        elem.click()
                        import time
                        time.sleep(0.4)
                        break
                expanded = self._get_element_text(self.video_selectors.video_description, timeout=2)
                if expanded and len(expanded) > len(raw):
                    raw = expanded
            except Exception as e:
                self.logger.debug(f"Error expanding description: {e}")

        return raw

    def get_video_description_parsed(self) -> Dict[str, Any]:
        """Get the full description split into clean text and hashtags.

        Returns::

            {
                'description_text': str | None,   # plain text without hashtags
                'hashtags': list[str],             # ['#miumiu', '#outfit', ...]
            }
        """
        raw = self.get_video_description_full()
        if not raw:
            return {'description_text': None, 'hashtags': []}
        return _parse_description(raw)

    def get_video_sound(self) -> Optional[str]:
        """Get the music/sound name from the sound button.

        Trill content-desc: 'Sound: Pretty (Sped Up) by MEYY'
        Returns the part after 'Sound: ', e.g. 'Pretty (Sped Up) by MEYY'.
        """
        desc = self._get_element_content_desc(_SOUND_SELECTORS, timeout=1)
        if desc:
            if desc.startswith('Sound: '):
                return desc[7:].strip()
            # Fallback: sometimes just the name
            if desc:
                return desc.strip()
        return None

    def get_author_profile_pic(self) -> Optional[str]:
        """Extract author profile picture as a base64 JPEG data URL.

        Finds the yx4 avatar ImageView bounds via XML dump,
        then crops a fresh screenshot to that region.

        Returns 'data:image/jpeg;base64,...' or None on failure.
        Only available when PIL/Pillow is installed.
        """
        try:
            import base64
            import io
            from lxml import etree
        except ImportError:
            return None

        try:
            xml = self.device.dump_hierarchy(compressed=False)
            if not xml:
                return None
            tree = etree.fromstring(xml.encode('utf-8'))

            bounds = None
            for pkg in _TIKTOK_PACKAGES:
                elems = tree.xpath(f'//*[@resource-id="{pkg}:id/yx4"]')
                if elems:
                    bounds_str = elems[0].get('bounds', '')
                    if bounds_str:
                        parts = bounds_str.replace('][', ',').replace('[', '').replace(']', '').split(',')
                        if len(parts) == 4:
                            bounds = {
                                'left': int(parts[0]), 'top': int(parts[1]),
                                'right': int(parts[2]), 'bottom': int(parts[3]),
                            }
                    break

            if not bounds:
                return None

            screenshot = self.device.screenshot_pil()
            if screenshot is None:
                return None

            padding = 2
            crop_box = (
                max(0, bounds['left'] - padding),
                max(0, bounds['top'] - padding),
                min(screenshot.size[0], bounds['right'] + padding),
                min(screenshot.size[1], bounds['bottom'] + padding),
            )
            cropped = screenshot.crop(crop_box)

            buf = io.BytesIO()
            cropped.convert('RGB').save(buf, format='JPEG', quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            self.logger.debug(
                f"📸 Author profile pic captured ({cropped.size[0]}x{cropped.size[1]}, {len(b64)//1024}KB)"
            )
            return f'data:image/jpeg;base64,{b64}'

        except Exception as e:
            self.logger.debug(f"Error capturing author profile pic: {e}")
            return None

    def get_video_like_count(self) -> Optional[str]:
        """Get current video like count.

        Tries text node first (musically), then parses content-desc
        (trill: 'Like video. 2 likes' or 'Like video. 1.2K likes').
        """
        count = self._get_element_text(self.video_selectors.like_count, timeout=1)
        if count:
            return count

        desc = self._get_element_content_desc(_LIKE_CONTENT_DESC_SELECTORS, timeout=1)
        if desc:
            m = re.search(r'Like video[.\s]+(.+?)\s+like', desc, re.IGNORECASE)
            if m:
                return m.group(1).strip()

        return None

    def get_video_comment_count(self) -> Optional[str]:
        """Get current video comment count.

        Trill: content-desc = 'Read or add comments. 0 comments'.
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

    def get_video_info(self, include_comment_count: bool = False,
                       full_description: bool = True) -> Dict[str, Any]:
        """Get all available info about current video.

        Args:
            include_comment_count: Also fetch comment count (slower).
            full_description: Expand truncated descriptions and parse hashtags.
        """
        if full_description:
            desc_parsed = self.get_video_description_parsed()
        else:
            raw = self.get_video_description()
            desc_parsed = _parse_description(raw) if raw else {'description_text': None, 'hashtags': []}

        info: Dict[str, Any] = {
            'author': self.get_video_author(),
            # Legacy field kept for backward compat (raw text)
            'description': desc_parsed.get('description_text'),
            'description_text': desc_parsed.get('description_text'),
            'hashtags': desc_parsed.get('hashtags', []),
            'sound': self.get_video_sound(),
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
        """Check if current video is an advertisement."""
        return self._element_exists(self.video_selectors.ad_label, timeout=1)



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
