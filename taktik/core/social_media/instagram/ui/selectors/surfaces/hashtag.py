from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class HashtagSelectors:
    """Sélecteurs pour le workflow hashtag."""

    # === Détection page hashtag ===
    _hashtag_header_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_title"]'
    ])

    @property
    def hashtag_header(self) -> List[str]:
        return self._hashtag_header_base + L("hashtag.hashtag_header")

    # === Extraction auteur Reel (content-desc "Reel by username") ===
    _reel_author_container_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/clips_media_component"]'
    ])

    @property
    def reel_author_container(self) -> List[str]:
        return self._reel_author_container_base + L("hashtag.reel_author_container")

HASHTAG_SELECTORS = HashtagSelectors()
