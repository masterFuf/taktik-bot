from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class HashtagSelectors:
    """Sélecteurs pour le workflow hashtag."""
    
    # === Détection page hashtag ===
    hashtag_header: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "posts")]',
        '//*[contains(@text, "publications")]',
        '//*[@resource-id="com.instagram.android:id/action_bar_title"]'
    ])
    
    # === Extraction auteur Reel (content-desc "Reel by username") ===
    reel_author_container: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Reel by")]',
        '//*[@resource-id="com.instagram.android:id/clips_media_component"]'
    ])

HASHTAG_SELECTORS = HashtagSelectors()
