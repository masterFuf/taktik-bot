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
    auxiliary_button: str = 'com.instagram.android:id/auxiliary_button'
    bb_primary_action: str = 'com.instagram.android:id/bb_primary_action'
    
    # === Navigation création ===
    next_button: str = 'com.instagram.android:id/next_button_textview'
    share_button: str = 'com.instagram.android:id/share_button'
    clips_right_action_button: str = 'com.instagram.android:id/clips_right_action_button'
    draft_headline: str = 'com.instagram.android:id/igds_headline_headline'
    draft_body: str = 'com.instagram.android:id/igds_headline_body'

    next_texts: List[str] = field(default_factory=lambda: [
        "Next",
        "Suivant",
    ])

    publish_texts: List[str] = field(default_factory=lambda: [
        "Share",
        "Partager",
        "Publier",
    ])

    story_publish_texts: List[str] = field(default_factory=lambda: [
        "Share",
        "Your story",
    ])

    popup_button_texts: List[str] = field(default_factory=lambda: [
        "OK",
        "Got it",
        "Continue",
        "Not now",
        "Skip",
    ])

    caption_placeholder_texts: List[str] = field(default_factory=lambda: [
        "Write a caption...",
    ])

    location_button_texts: List[str] = field(default_factory=lambda: [
        "Add location",
    ])

    next_descriptions: List[str] = field(default_factory=lambda: [
        "Next",
        "Suivant",
    ])

    edit_video_indicators: List[str] = field(default_factory=lambda: [
        "Edit video",
        "Modifier la vidéo",
    ])
    
    post_type_texts: List[str] = field(default_factory=lambda: [
        "POST",
    ])

    reel_type_texts: List[str] = field(default_factory=lambda: [
        "REEL",
        "Reels",
        "REELS",
    ])

    story_type_texts: List[str] = field(default_factory=lambda: [
        "STORY",
    ])

    reel_draft_headlines: List[str] = field(default_factory=lambda: [
        "Keep editing your draft?",
        "Continuer la modification de votre brouillon ?",
    ])

    reel_draft_bodies: List[str] = field(default_factory=lambda: [
        "If you start a new video, this draft will be saved.",
        "Si vous commencez une nouvelle vidÃ©o, ce brouillon sera enregistrÃ©.",
    ])

    reel_draft_start_new_texts: List[str] = field(default_factory=lambda: [
        "Start new video",
        "Commencer une nouvelle vidÃ©o",
    ])

    # === Champs de texte ===
    caption_text_view: str = 'com.instagram.android:id/caption_text_view'
    caption_input_text_view: str = 'com.instagram.android:id/caption_input_text_view'
    
    # === Feed interactions ===
    feed_like_button: str = 'com.instagram.android:id/row_feed_button_like'
    feed_profile_name: str = 'com.instagram.android:id/row_feed_photo_profile_name'

CONTENT_CREATION_SELECTORS = ContentCreationSelectors()
