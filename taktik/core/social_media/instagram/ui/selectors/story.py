from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class StorySelectors:
    """Sélecteurs pour les stories."""
    
    # === Éléments de base ===
    story_ring: str = '//android.view.View[contains(@content-desc, "story") or contains(@content-desc, "story")]'
    story_image: str = '//android.widget.ImageView[contains(@resource-id, "reel_media_image")]'
    story_video: str = '//android.widget.VideoView[contains(@resource-id, "reel_media_video")]'
    
    # === Navigation ===
    next_story: str = '//android.widget.FrameLayout[contains(@resource-id, "story_viewer_container")]//android.widget.ImageView[contains(@content-desc, "Suivant") or contains(@content-desc, "Next")]'
    close_story: str = '//android.widget.ImageView[contains(@content-desc, "Fermer") or contains(@content-desc, "Close")]'
    
    # === Détection du nombre de stories ===
    # Viewer de story - contient "story X of Y" dans le content-desc
    story_viewer_text_container: str = '//*[@resource-id="com.instagram.android:id/reel_viewer_text_container"]'
    
    # Header de story avec username et timestamp
    story_viewer_header: str = '//*[@resource-id="com.instagram.android:id/reel_viewer_header"]'
    story_viewer_title: str = '//*[@resource-id="com.instagram.android:id/reel_viewer_title"]'
    story_viewer_timestamp: str = '//*[@resource-id="com.instagram.android:id/reel_viewer_timestamp"]'
    
    # Barre de progression des stories
    story_progress_bar: str = '//*[@resource-id="com.instagram.android:id/reel_viewer_progress_bar"]'
    
    # Actions sur story
    story_like_button: str = '//*[@resource-id="com.instagram.android:id/toolbar_like_button"]'
    story_share_button: str = '//*[@resource-id="com.instagram.android:id/toolbar_reshare_button"]'
    story_message_composer: str = '//*[@resource-id="com.instagram.android:id/message_composer_container"]'

STORY_SELECTORS = StorySelectors()
