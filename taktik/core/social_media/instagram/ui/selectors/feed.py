from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class FeedSelectors:
    """Sélecteurs pour le feed principal Instagram."""
    
    # === Conteneurs de posts dans le feed ===
    post_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_imageview"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_profile_header"]'
    ])
    
    # === Username de l'auteur du post ===
    post_author_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_username"]'
    ])
    
    # === Avatar de l'auteur ===
    post_author_avatar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_imageview"]'
    ])
    
    # === Indicateurs de post sponsorisé ===
    sponsored_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Sponsorisé")]',
        '//*[contains(@text, "Sponsored")]',
        '//*[contains(@text, "Publicité")]',
        '//*[contains(@text, "Ad")]'
    ])
    
    # === Indicateurs de Reel dans le feed ===
    reel_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Reel")]',
        '//*[@resource-id="com.instagram.android:id/clips_video_container"]',
        '//*[@resource-id="com.instagram.android:id/clips_viewer_view_pager"]',
        '//*[@resource-id="com.instagram.android:id/clips_audio_attribution_button"]'
    ])
    
    # === Compteur de likes dans le feed ===
    likes_count_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_textview_likes"]',
        '//*[contains(@text, "J\'aime")]',
        '//*[contains(@text, "likes")]'
    ])
    
    # === Bouton like dans le feed ===
    like_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]',
        '//*[contains(@content-desc, "J\'aime")]',
        '//*[contains(@content-desc, "Like")]',
        '//*[@resource-id="com.instagram.android:id/like_button"]'
    ])
    
    # === Détection post déjà liké ===
    already_liked_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Unlike")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Ne plus aimer")]',
        '//*[contains(@content-desc, "Unlike")]',
        '//*[contains(@content-desc, "Ne plus aimer")]'
    ])
    
    # === Bouton commentaire dans le feed ===
    comment_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]',
        '//*[contains(@content-desc, "Comment")]',
        '//*[contains(@content-desc, "Commenter")]'
    ])
    
    # === Champ de saisie commentaire ===
    comment_input: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_edittext"]',
        '//*[contains(@text, "Add a comment")]',
        '//*[contains(@text, "Ajouter un commentaire")]',
        '//android.widget.EditText'
    ])
    
    # === Bouton envoyer commentaire ===
    comment_send_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_post_button_click_area"]',
        '//*[contains(@content-desc, "Post")]',
        '//*[contains(@content-desc, "Publier")]',
        '//*[contains(@text, "Post")]'
    ])

FEED_SELECTORS = FeedSelectors()
