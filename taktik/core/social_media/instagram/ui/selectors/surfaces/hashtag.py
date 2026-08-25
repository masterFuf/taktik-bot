from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class HashtagSelectors:
    """Selectors for the hashtag workflow."""

    # === Détection page hashtag ===
    # IG 442 removed `action_bar_title` from this screen: the hashtag is shown in the action
    # bar's SEARCH FIELD instead (verified on device -- 0 matches for the old id, the field
    # holding "#voyage"). The old id stays first for older builds. Note this is the TITLE, not
    # a surface proof: the same field exists on the search screen, so use
    # `DETECTION_SELECTORS.hashtag_page_indicators` to know where you are.
    _hashtag_header_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_title"]',
        '//*[contains(@resource-id, "action_bar_search_edit_text") and starts-with(@text, "#")]',
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
