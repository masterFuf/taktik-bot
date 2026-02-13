from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class ContentCreationSelectors:
    """Sélecteurs pour la création de contenu (posts, stories, reels)."""
    
    # === Tab de création ===
    creation_tab: str = 'com.instagram.android:id/creation_tab'
    
    # === Galerie ===
    gallery_grid_item: str = 'com.instagram.android:id/gallery_grid_item_thumbnail'
    
    # === Boutons de popup ===
    primary_button: str = 'com.instagram.android:id/primary_button'
    bb_primary_action: str = 'com.instagram.android:id/bb_primary_action'
    
    # === Navigation création ===
    next_button: str = 'com.instagram.android:id/next_button_textview'
    
    # === Champs de texte ===
    caption_text_view: str = 'com.instagram.android:id/caption_text_view'
    caption_input_text_view: str = 'com.instagram.android:id/caption_input_text_view'
    
    # === Feed interactions ===
    feed_like_button: str = 'com.instagram.android:id/row_feed_button_like'
    feed_profile_name: str = 'com.instagram.android:id/row_feed_photo_profile_name'

CONTENT_CREATION_SELECTORS = ContentCreationSelectors()
