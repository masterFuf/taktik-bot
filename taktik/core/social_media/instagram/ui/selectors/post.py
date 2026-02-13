from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class PostSelectors:
    """Sélecteurs pour les publications (posts et reels)."""
    
    # === Conteneurs de base ===
    post_container: str = '//androidx.recyclerview.widget.RecyclerView/android.widget.FrameLayout'
    post_image: str = '//android.widget.ImageView[contains(@resource-id, "image_view")]'
    post_video: str = '//android.widget.VideoView'
    
    username: str = '//android.widget.TextView[contains(@resource-id, "row_feed_photo_profile_name")]'
    caption: str = '//android.widget.TextView[contains(@resource-id, "row_feed_comment_textview_comment")]'
    like_count: str = '//android.widget.TextView[contains(@resource-id, "row_feed_textview_likes")]'
    comment_count: str = '//android.widget.TextView[contains(@resource-id, "row_feed_textview_comment_count")]'
    
    # === Éléments spéciaux ===
    carousel_indicator: str = '//androidx.viewpager.widget.ViewPager/following-sibling::*[1]'
    reels_player: str = '//android.view.ViewGroup[contains(@resource-id, "reel_player_container")]'
    first_post_grid: str = '//*[@resource-id="com.instagram.android:id/image_button"]'
    
    # === Extraction d'auteur (PostUrlBusiness) ===
    profile_image_selectors: List[str] = field(default_factory=lambda: [
        # Reel-specific selector (check first)
        '//*[@resource-id="com.instagram.android:id/clips_author_profile_pic"]',
        # Regular post selector
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_imageview"]'
    ])
    
    header_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_profile_header"]'
    ])
    
    username_extraction_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
        '//*[@resource-id="com.instagram.android:id/username"]',
        '//*[@resource-id="com.instagram.android:id/profile_name"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_username"]',
        # Pour les reels
        '//*[@resource-id="com.instagram.android:id/clips_author_info"]//android.widget.TextView',
        # Sélecteurs génériques
        '//android.widget.TextView[starts-with(@text, "@")]',
        '//android.widget.TextView[contains(@content-desc, "nom d\'utilisateur")]'
    ])
    
    # === Détection et extraction de likes ===
    like_count_selectors: List[str] = field(default_factory=lambda: [
        # PRIORITY 1: Reel-specific selector (most specific, check first)
        '//*[@resource-id="com.instagram.android:id/like_count"]',
        # PRIORITY 2: Regular post selectors
        # Sélecteur le plus fiable : TOUJOURS le premier Button avec texte (= likes)
        # Structure Instagram : ViewGroup[0]=J'aime, Button[1]=Likes, ViewGroup[2]=Commentaire, Button[3]=Nb commentaires, Button[4-6]=Partages
        '(//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]/android.widget.Button[@text])[1]',
        # Fallback : bouton juste après le conteneur du bouton J'aime
        '//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]/*[@resource-id="com.instagram.android:id/row_feed_button_like"]/parent::*/following-sibling::android.widget.Button[@text][1]',
        # Autres fallbacks pour compatibilité
        '//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]/android.widget.Button[@text and @clickable="true"][1]',
        '//*[contains(@content-desc, "J\'aime")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_like_count_facepile"]'
    ])
    
    button_like_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]//android.widget.Button[@text and @clickable="true"]',
        '//android.widget.Button[@clickable="true" and @text]',
        '//android.widget.Button[@clickable="true" and string-length(@text) > 0 and string-length(@text) < 10]'
    ])
    
    photo_like_selectors: List[str] = field(default_factory=lambda: [
        # Sélecteur spécifique pour l'élément avec content-desc contenant les métadonnées
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_imageview" and contains(@content-desc, "J\'aime")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_imageview" and contains(@content-desc, "likes")]',
        # Fallback plus général
        '//*[contains(@content-desc, "J\'aime") and contains(@content-desc, "commentaire")]',
        '//*[contains(@content-desc, "likes") and contains(@content-desc, "comment")]',
        # Ancien sélecteur générique en dernier recours
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_imageview"]'
    ])
    
    # === Reels spécifiques ===
    reel_like_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/like_count"]',
        '//*[@resource-id="com.instagram.android:id/likes_count"]',
        '//android.widget.TextView[contains(@text, "J\'aime")]',
        '//android.widget.TextView[contains(@text, "likes")]',
        # Sélecteurs pour Reels en mode feed (bouton sans resource-id)
        '//android.widget.Button[@clickable="true" and string-length(@text) > 0 and string-length(@text) < 10]',
        '//android.widget.Button[contains(@text, ",")]',  # Ex: "1,561"
        '//android.widget.Button[contains(@text, "K")]',  # Ex: "15K"
        '//android.widget.Button[contains(@text, "M")]'   # Ex: "1.5M"
    ])
    
    reel_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Reel de")]',
        '//*[@resource-id="com.instagram.android:id/clips_single_media_component"]',
        '//*[@resource-id="com.instagram.android:id/clips_viewer_video_layout"]',
        '//*[@resource-id="com.instagram.android:id/clips_video_container"]',
        '//*[contains(@content-desc, "Reel by")]',
        '//*[@resource-id="com.instagram.android:id/clips_video_player"]'
    ])
    
    # === Sélecteurs automation.py ===
    automation_reel_specific_indicators: List[str] = field(default_factory=lambda: [
        "//android.widget.TextView[@text='Reel']",
        "//android.widget.TextView[contains(@text, 'reel')]",
        "//android.view.ViewGroup[@content-desc='Reel']",
        "//android.widget.Button[@content-desc='Like this reel']",
        "//android.widget.Button[@content-desc='Share this reel']",
        "//android.widget.TextView[contains(@text, 'Original audio')]",
        "//android.widget.TextView[contains(@text, 'Audio original')]"
    ])
    
    video_controls: List[str] = field(default_factory=lambda: [
        "//android.widget.Button[@content-desc='Play']",
        "//android.widget.Button[@content-desc='Pause']"
    ])
    
    classic_post_indicators: List[str] = field(default_factory=lambda: [
        "//android.widget.TextView[contains(@text, 'View all') and contains(@text, 'comment')]",
        "//android.widget.TextView[contains(@text, 'Voir les') and contains(@text, 'commentaire')]",
        "//android.widget.Button[@content-desc='Comment']",
        "//android.widget.Button[@content-desc='Commenter']"
    ])
    
    post_elements: List[str] = field(default_factory=lambda: [
        "//android.widget.TextView[contains(@text, 'like') or contains(@text, 'J\\'aime')]",
        "//android.widget.Button[@content-desc='Like']",
        "//android.widget.Button[@content-desc='Comment']"
    ])
    
    automation_like_indicators: List[str] = field(default_factory=lambda: [
        "//android.widget.Button[contains(@text, '1') or contains(@text, '2') or contains(@text, '3') or contains(@text, '4') or contains(@text, '5') or contains(@text, '6') or contains(@text, '7') or contains(@text, '8') or contains(@text, '9')]",
        "//android.widget.TextView[contains(@text, 'like') and (contains(@text, '1') or contains(@text, '2') or contains(@text, '3') or contains(@text, '4') or contains(@text, '5') or contains(@text, '6') or contains(@text, '7') or contains(@text, '8') or contains(@text, '9'))]",
        "//android.widget.TextView[contains(@text, 'J\'aime') and (contains(@text, '1') or contains(@text, '2') or contains(@text, '3') or contains(@text, '4') or contains(@text, '5') or contains(@text, '6') or contains(@text, '7') or contains(@text, '8') or contains(@text, '9'))]",
        "//android.view.ViewGroup[@content-desc='Like']/following-sibling::android.widget.Button[contains(@text, '1') or contains(@text, '2') or contains(@text, '3') or contains(@text, '4') or contains(@text, '5') or contains(@text, '6') or contains(@text, '7') or contains(@text, '8') or contains(@text, '9')]"
    ])
    
    automation_like_count_selectors: List[str] = field(default_factory=lambda: [
        "//android.view.ViewGroup[@content-desc='Like']/following-sibling::android.widget.Button[1]",
        "//android.widget.Button[matches(@text, '^[0-9]+$')]",
        "//android.view.ViewGroup[@resource-id='com.instagram.android:id/row_feed_button_like']/parent::*/following-sibling::android.widget.Button",
        "//android.widget.TextView[contains(@text, 'like') and not(contains(@text, 'comment'))]",
        "//android.widget.TextView[contains(@text, 'J\'aime')]",
        "//android.widget.TextView[@resource-id='com.instagram.android:id/row_feed_textview_likes']"
    ])
    
    heart_icon_selector: str = "//android.view.ViewGroup[@content-desc='Like'] | //android.view.ViewGroup[@resource-id='com.instagram.android:id/row_feed_button_like']"
    
    # === Sélecteurs like_business.py ===
    like_button_advanced_selectors: List[str] = field(default_factory=lambda: [
        # ViewGroup cliquable qui contient le bouton like
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]/parent::*[@clickable="true"]',
        # Fallback sur le ViewGroup parent
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]/../..',
        # Sélecteurs génériques
        '//*[contains(@content-desc, "Like")][@clickable="true"]',
        '//*[contains(@content-desc, "J\'aime")][@clickable="true"]'
    ])
    
    post_view_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_share"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]',
        '//*[contains(@content-desc, "Like")]',
        '//*[contains(@content-desc, "Comment")]'
    ])
    
    next_post_button_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@content-desc, "Next")]',
        '//android.widget.ImageView[contains(@content-desc, "Next")]'
    ])
    
    back_button_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[@resource-id="com.instagram.android:id/action_bar_button_back"]',
        '//android.widget.ImageView[@content-desc="Back"]',
        '//*[@content-desc="Back"]'
    ])
    
    photo_imageview_selector: str = '//*[@resource-id="com.instagram.android:id/row_feed_photo_imageview"]'
    
    # === Post Metadata Extraction (for hashtag workflow) ===
    # Auteur du post (Reel view)
    reel_author_username_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/clips_author_username"]',
        '//*[@resource-id="com.instagram.android:id/clips_author_info_component"]//android.widget.Button',
        '//*[contains(@content-desc, "Profile picture of")]/..//android.widget.Button[@text]',
    ])
    
    # Caption du post (Reel view)
    # La caption est dans un ViewGroup imbriqué avec content-desc contenant le texte + hashtags
    # Note: La caption peut être rétractée (avec "…"), il faut cliquer dessus pour l'ouvrir
    reel_caption_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/clips_caption_component"]//android.widget.ScrollView//android.view.ViewGroup[@content-desc]',
        '//*[@resource-id="com.instagram.android:id/clips_caption_component"]//android.view.ViewGroup[@content-desc and @clickable="true"]',
        '//*[@resource-id="com.instagram.android:id/clips_caption_component"]//*[@content-desc]',
    ])
    
    # Date du post (Reel view) - visible quand la caption est ouverte
    # Format: "31 October 2025"
    reel_date_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/clips_caption_component"]//android.view.ViewGroup[@content-desc and contains(@content-desc, " ") and not(contains(@content-desc, "#"))]',
        '//*[@resource-id="com.instagram.android:id/clips_caption_component"]//android.view.ViewGroup[@text]',
    ])
    
    # Auteur du post (Regular post view)
    post_author_username_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_username"]',
    ])
    
    # Caption du post (Regular post view)
    post_caption_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_comment_textview_comment"]',
    ])
    
    # Likes count (for both views)
    post_likes_count_selectors: List[str] = field(default_factory=lambda: [
        # Reel view - content-desc contains "The like number is X"
        '//*[@resource-id="com.instagram.android:id/like_count"]',
        # Regular post view
        '//*[@resource-id="com.instagram.android:id/row_feed_textview_likes"]',
    ])
    
    # Comments count (for both views)
    post_comments_count_selectors: List[str] = field(default_factory=lambda: [
        # Reel view - content-desc contains "Comment number isX"
        '//*[@resource-id="com.instagram.android:id/comment_count"]',
        # Regular post view
        '//*[@resource-id="com.instagram.android:id/row_feed_textview_comment_count"]',
    ])
    
    reel_indicators_like_business: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Reel")]',
        '//*[contains(@content-desc, "reel")]',
        '//*[@resource-id="com.instagram.android:id/clips_video_container"]',
        '//*[@resource-id="com.instagram.android:id/video_container"]'
    ])
    
    like_count_button_selector: str = '//android.widget.Button[@text and string-length(@text) > 0]'
    
    # === Sélecteurs hashtag_business.py ===
    hashtag_post_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/image_button"]',
        '//*[@resource-id="com.instagram.android:id/layout_container" and @clickable="true"]',
        '//*[@resource-id="com.instagram.android:id/image_preview"]'
    ])
    
    reel_player_indicators: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Audio"]',
        '//*[@content-desc="Couper le son"]',
        '//*[@content-desc="Activer le son"]',
        '//*[contains(@content-desc, "Turn sound on")]',
        '//*[contains(@content-desc, "Turn sound off")]',
        '//*[contains(@content-desc, "Musique")]',
        '//*[@resource-id="com.instagram.android:id/clips_video_player"]'
    ])
    
    carousel_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/carousel_media_group"]',
        '//*[@resource-id="com.instagram.android:id/carousel_viewpager"]',
        '//*[@resource-id="com.instagram.android:id/carousel_video_media_group"]'
    ])
    
    post_detail_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_imageview"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_profile_header"]',
        '//*[@content-desc="J\'aime"]',
        '//*[@content-desc="Like"]',
        '//*[@content-desc="Commenter"]',
        '//*[@content-desc="Comment"]',
        '//*[contains(@content-desc, "aime")]'
    ])
    
    like_button_indicators: List[str] = field(default_factory=lambda: [
        "//android.widget.Button[contains(@content-desc, 'J')]",  # "J'aime"
        "//android.widget.Button[contains(@content-desc, 'aime')]",
        "//android.widget.Button[contains(@content-desc, 'like')]",
        "//android.widget.ImageView[contains(@content-desc, 'aime')]",  # Corrigé : évite l'apostrophe
        "//*[contains(@resource-id, 'row_feed_button_like')]"
    ])
    
    comment_button_indicators: List[str] = field(default_factory=lambda: [
        "//android.widget.Button[contains(@content-desc, 'Comment')]",
        "//android.widget.Button[contains(@content-desc, 'commentaire')]",
        "//*[contains(@resource-id, 'row_feed_button_comment')]"
    ])
    
    # === Commentaires ===
    photo_comment_selectors: List[str] = field(default_factory=lambda: [
        # Sélecteur spécifique pour l'élément avec content-desc contenant les métadonnées
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_imageview" and contains(@content-desc, "commentaire")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_imageview" and contains(@content-desc, "comment")]',
        # Fallback plus général
        '//*[contains(@content-desc, "J\'aime") and contains(@content-desc, "commentaire")]',
        '//*[contains(@content-desc, "likes") and contains(@content-desc, "comment")]',
        # Ancien sélecteur générique en dernier recours
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_imageview"]'
    ])
    
    comment_button_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]/parent::*[@clickable="true"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]',
        '//*[contains(@content-desc, "Comment") and @clickable="true"]',
        '//android.widget.ImageView[contains(@content-desc, "Commenter")]',
        '//android.widget.ImageView[contains(@content-desc, "Comment")]'
    ])
    
    comment_field_selector: str = '//*[@resource-id="com.instagram.android:id/layout_comment_thread_edittext"]'
    post_comment_button_selector: str = '//*[@resource-id="com.instagram.android:id/layout_comment_thread_post_button_icon"]'
    
    # === "Liked by" text selectors (for opening likers list from post view) ===
    liked_by_selectors: List[str] = field(default_factory=lambda: [
        '//*[starts-with(@text, "Liked by")]',
        '//*[starts-with(@text, "Aimé par")]',
        '//*[starts-with(@text, "liked by")]',
    ])
    
    # === Comments list & username extraction ===
    comments_list_resource_id: str = 'com.instagram.android:id/sticky_header_list'
    
    comment_username_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/sticky_header_list"]//android.view.ViewGroup[@text]/android.widget.Button[@text]',
        '//*[@resource-id="com.instagram.android:id/sticky_header_list"]//android.widget.Button[@text]',
        '//*[@resource-id="com.instagram.android:id/row_comment_textview_comment_container"]//android.widget.Button',
    ])
    
    comments_view_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/sticky_header_list"]',
        '//*[contains(@text, "Comments")]',
        '//*[contains(@content-desc, "Add a comment")]',
    ])
    
    comment_sort_button: str = '//*[@content-desc="For you"]'
    
    expand_replies_selector: str = '//*[contains(@content-desc, "View") and contains(@content-desc, "more repl")]'
    
    # === Autres éléments posts ===
    video_player_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.VideoView',
        '//android.view.TextureView',
        '//android.widget.ImageView[contains(@content-desc, "vidéo")]',
        '//android.widget.ImageView[contains(@content-desc, "video")]'
    ])
    
    media_elements_selector: str = '//android.widget.ImageView | //android.widget.VideoView'
    
    timestamp_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@content-desc, "heure")]',
        '//android.widget.TextView[contains(@content-desc, "min")]',
        '//android.widget.TextView[contains(@content-desc, "h")]',
        '//android.widget.TextView[contains(@content-desc, "jour")]',
        '//android.widget.TextView[contains(@content-desc, "week")]',
        '//android.widget.TextView[contains(@content-desc, "month")]',
        '//*[contains(@content-desc, "heure")]',
        '//*[contains(@content-desc, "min")]'
    ])
    
    save_button_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[contains(@content-desc, "Enregistrer")]',
        '//android.widget.ImageView[contains(@content-desc, "Save")]',
        '//*[contains(@resource-id, "row_feed_button_save")]'
    ])
    
    share_button_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[contains(@content-desc, "Partager")]',
        '//android.widget.ImageView[contains(@content-desc, "Share")]',
        '//*[contains(@resource-id, "share_button")]'
    ])
    
    # === Caption selectors ===
    caption_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_comment_text"]',
        '//*[contains(@resource-id, "caption")]'
    ])
    
    # === Likes count selectors (for opening likers list) ===
    likes_count_click_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "J\'aime")]',
        '//*[contains(@text, "likes")]',
        '//*[contains(@resource-id, "like_count")]'
    ])
    
    # === Send/Post button selectors ===
    send_post_button_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Publier")]',
        '//*[contains(@content-desc, "Post")]',
        '//*[contains(@text, "Publier")]',
        '//*[contains(@text, "Post")]',
        '//*[contains(@content-desc, "Share")]',
        '//*[contains(@text, "Share")]'
    ])

POST_SELECTORS = PostSelectors()
