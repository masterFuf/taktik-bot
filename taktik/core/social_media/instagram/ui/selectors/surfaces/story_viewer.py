from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class StorySelectors:
    """Sélecteurs pour les stories."""
    
    # === Éléments de base ===
    story_ring: str = '//android.view.View[contains(@content-desc, "story") or contains(@content-desc, "story")]'
    story_image: str = '//android.widget.ImageView[contains(@resource-id, "reel_media_image")]'
    story_video: str = '//android.widget.VideoView[contains(@resource-id, "reel_media_video")]'

    # === Home feed story tray ===
    feed_story_tray: str = '//*[contains(@resource-id, "reels_tray_container")]'
    feed_story_recycler: str = '//*[contains(@content-desc, "conteneur barre des reels") or contains(@content-desc, "reels tray")]'
    feed_story_buttons: str = '//*[contains(@resource-id, "reels_tray_container")]//android.widget.Button[contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "story")]'
    feed_unseen_story_buttons: str = '//*[contains(@resource-id, "reels_tray_container")]//android.widget.Button[contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "story") and (contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "non vus") or contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "unseen"))]'

    # === Profile / highlights ===
    profile_unseen_story_avatar: str = '//*[contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "unseen story")]'
    highlight_tray: str = '//*[contains(@resource-id, "highlights_tray")]'
    highlight_recycler: str = '//*[contains(@resource-id, "highlights_reel_tray_recycler_view")]'
    highlight_buttons: str = '//*[contains(@resource-id, "highlights_reel_tray_recycler_view")]//android.widget.Button[contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "story")]'
    highlight_images: str = '//*[contains(@resource-id, "highlights_reel_tray_recycler_view")]//*[contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "highlight story")]'
    
    # === Navigation ===
    next_story: str = '//android.widget.FrameLayout[contains(@resource-id, "story_viewer_container")]//android.widget.ImageView[contains(@content-desc, "Suivant") or contains(@content-desc, "Next")]'
    close_story: str = '//android.widget.ImageView[contains(@content-desc, "Fermer") or contains(@content-desc, "Close")]'
    
    # === Détection du nombre de stories ===
    # Viewer de story - contient "story X of Y" dans le content-desc
    story_viewer_text_container: str = '//*[contains(@resource-id, "reel_viewer_text_container")]'
    
    # Header de story avec username et timestamp
    story_viewer_header: str = '//*[contains(@resource-id, "reel_viewer_header")]'
    story_viewer_title: str = '//*[contains(@resource-id, "reel_viewer_title")]'
    story_viewer_timestamp: str = '//*[contains(@resource-id, "reel_viewer_timestamp")]'
    story_author_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "reel_viewer_title")]',
        '//*[contains(@resource-id, "story_username")]',
        '//*[contains(@resource-id, "reel_viewer_username")]',
        '//*[contains(@resource-id, "username")]',
    ])
    
    # Barre de progression des stories
    story_progress_bar: str = '//*[contains(@resource-id, "reel_viewer_progress_bar")]'
    story_viewer_root: str = '//*[contains(@resource-id, "reel_viewer_root")]'

    # === Pub / story sponsorisee (a NE PAS traiter comme une story d'ami) ===
    story_sponsored_label: str = '//*[contains(@resource-id, "reel_item_sponsored_label") or contains(@content-desc, "sponsored story") or contains(@content-desc, "story sponsorisée") or contains(@content-desc, "Sponsorisé")]'
    
    # Actions sur story
    story_like_button: str = '//*[contains(@resource-id, "toolbar_like_button")]'
    story_share_button: str = '//*[contains(@resource-id, "toolbar_reshare_button")]'
    story_message_composer: str = '//*[contains(@resource-id, "message_composer_container") or contains(@resource-id, "reel_viewer_message_composer")]'
    story_reaction_toolbar: str = '//*[contains(@resource-id, "reel_reaction_toolbar")]'
    story_reaction_emojis: str = '//*[contains(@resource-id, "story_reactions_emoji")]'

STORY_SELECTORS = StorySelectors()
