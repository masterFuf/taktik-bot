"""
Sélecteurs UI pour Instagram - Organisés par fonctionnalité.

Ce module contient tous les sélecteurs d'éléments d'interface utilisateur pour Instagram,
organisés de manière logique par catégories fonctionnelles.

Structure:
- Navigation & Boutons système
- Profils utilisateurs  
- Publications (Posts & Reels)
- Stories
- Messages directs
- Popups & Modales
- Scroll & Chargement
- Debug & Utilitaires
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

# =============================================================================
# 🧭 NAVIGATION & BOUTONS SYSTÈME
# =============================================================================

@dataclass
class NavigationSelectors:
    """Sélecteurs pour la navigation et les boutons système."""
    
    # === Navigation principale (listes pour fallbacks) ===
    home_tab: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Accueil")]',
        '//*[contains(@content-desc, "Home")]',
        '//*[contains(@resource-id, "tab_bar_icon") and contains(@content-desc, "Accueil")]',
        '//*[contains(@resource-id, "bottom_navigation_icon") and contains(@content-desc, "Home")]'
    ])
    
    search_tab: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Rechercher")]',
        '//*[contains(@content-desc, "Search")]',
        '//*[contains(@resource-id, "tab_bar_icon") and contains(@content-desc, "Rechercher")]'
    ])
    
    reels_tab: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Reels")]',
        '//*[contains(@content-desc, "Shorts")]'
    ])
    
    activity_tab: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Activité")]',
        '//*[contains(@content-desc, "Activity")]'
    ])
    
    profile_tab: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "profile_tab")]',
        '//*[contains(@resource-id, "tab_profile")]',
        '//*[contains(@resource-id, "tab_bar_profile")]',
        '//*[contains(@content-desc, "Profile") and contains(@class, "ImageView")]',
        '//*[contains(@content-desc, "Profil") and contains(@class, "ImageView")]',
        '//*[contains(@content-desc, "Profil")]',
        '//*[contains(@content-desc, "Profile")]',
        '(//android.widget.FrameLayout[contains(@resource-id, "tab_")])[last()]',
        '//*[contains(@resource-id, "tab") and position()=5]',
        '//*[contains(@resource-id, "tab_bar_icon") and contains(@content-desc, "Profil")]'
    ])
    
    # === Boutons système (listes pour fallbacks) ===
    back_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Retour")]',
        '//*[contains(@content-desc, "Back")]',
        '//*[contains(@content-desc, "Précédent")]'
    ])
    
    close_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Fermer")]',
        '//*[contains(@content-desc, "Close")]',
        '//*[contains(@content-desc, "Annuler")]',
        '//*[contains(@content-desc, "Cancel")]'
    ])
    
    # === Boutons de retour multiples ===
    back_buttons: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_button_back"]',
        '//*[@content-desc="Back"]',
        '//*[@resource-id="com.instagram.android:id/action_bar_button_back" and @content-desc="Back"]'
    ])
    
    # === Onglets de profil ===
    posts_tab_options: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Posts"]',
        '//*[@text="Posts"]',
        '//*[@resource-id="com.instagram.android:id/profile_tab_layout"]//android.widget.ImageView[1]',
        '//android.widget.ImageView[@content-desc="Grid view"]'
    ])

@dataclass
class ButtonSelectors:
    """Sélecteurs pour les boutons d'interaction courants."""
    
    # === Boutons d'interaction posts (listes pour fallbacks) ===
    like_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "J\'aime")]',
        '//*[contains(@content-desc, "Like")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]'
    ])
    
    comment_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Commentaire")]',
        '//*[contains(@content-desc, "Comment")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]'
    ])
    
    save_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Ajouter aux enregistrements")]',
        '//*[contains(@content-desc, "Save")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_save"]'
    ])
    
    share_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Envoyer la publication")]',
        '//*[contains(@content-desc, "Share")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_share"]'
    ])

# =============================================================================
# 👤 PROFILS UTILISATEURS
# =============================================================================

@dataclass
class ProfileSelectors:
    """Sélecteurs pour les profils utilisateurs."""
    
    # === Informations de base (listes pour fallbacks) ===
    username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_title"]',
        '//*[contains(@resource-id, "action_bar_title")]'
    ])
    
    bio: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_header_bio_text"]',
        '//*[contains(@resource-id, "profile_header_bio_text")]'
    ])
    
    posts_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_profile_header_posts_container"]',
        '//*[contains(@resource-id, "posts_container")]'
    ])
    
    followers_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_profile_header_followers_container"]',
        '//*[contains(@resource-id, "followers_container")]'
    ])
    
    following_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_profile_header_following_container"]',
        '//*[contains(@resource-id, "following_container")]'
    ])
    
    # === Boutons d'action (listes pour fallbacks) ===
    follow_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_header_follow_button"]',
        '//*[@resource-id="com.instagram.android:id/follow_button"]',
        '//*[contains(@text, "Suivre") and not(contains(@text, "Abonné"))]',
        '//*[contains(@text, "Follow") and not(contains(@text, "Following"))]'
    ])
    
    following_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Abonné")]',
        '//*[contains(@text, "Following")]',
        '//*[contains(@text, "Suivi(e)")]'
    ])
    
    message_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Message")]',
        '//*[contains(@text, "Envoyer un message")]',
        '//*[@resource-id="com.instagram.android:id/profile_header_message_button"]'
    ])
    
    # === Onglets du profil ===
    posts_tab: str = '//android.widget.LinearLayout[contains(@content-desc, "Publications") or contains(@content-desc, "Posts")]'
    igtv_tab: str = '//android.widget.LinearLayout[contains(@content-desc, "IGTV")]'
    saved_tab: str = '//android.widget.LinearLayout[contains(@content-desc, "Enregistré") or contains(@content-desc, "Saved")]'
    tagged_tab: str = '//android.widget.LinearLayout[contains(@content-desc, "Photos de") or contains(@content-desc, "Photos with")]'
    
    # === Détection de profils privés ===
    zero_posts_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_header_familiar_post_count_value" and @text="0"]',
        '//*[contains(@content-desc, "0publications")]',
        '//*[contains(@content-desc, "0 publications")]'
    ])
    
    private_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "privé")]',
        '//*[contains(@text, "Private")]', 
        '//*[contains(@text, "private")]',
        '//*[contains(@text, "Follow to see")]',
        '//*[contains(@text, "Suivre pour voir")]',
        '//*[contains(@content-desc, "privé")]',
        '//*[contains(@content-desc, "Private")]'
    ])
    
    # === Boutons multiples (écrans de suggestions) ===
    follow_buttons: str = '//android.widget.Button[contains(@text, "Follow")]'
    suivre_buttons: str = '//android.widget.Button[contains(@text, "Suivre")]'
    
    # === Sélecteurs avancés pour follow (éviter followers/following) ===
    advanced_follow_selectors: List[str] = field(default_factory=lambda: [
        # Bouton Follow principal dans le header du profil
        '//android.widget.Button[@resource-id="com.instagram.android:id/profile_header_follow_button"]',
        # Bouton Follow dans la barre d'action (apparaît après scroll dans la grille)
        '//android.widget.Button[@resource-id="com.instagram.android:id/follow_button"]',
        # Sélecteurs avec contraintes pour éviter les liens followers/following
        '//android.widget.Button[@text="Follow" and not(contains(@content-desc, "followers")) and not(contains(@content-desc, "following"))]',
        '//android.widget.Button[@text="Suivre" and not(contains(@content-desc, "followers")) and not(contains(@content-desc, "following"))]',
        # Sélecteurs avec classe Button explicite
        '//android.widget.Button[contains(@content-desc, "Follow") and not(contains(@content-desc, "followers"))]',
        '//android.widget.Button[contains(@content-desc, "Suivre") and not(contains(@content-desc, "followers"))]'
    ])

# =============================================================================
# 📱 PUBLICATIONS (POSTS & REELS)
# =============================================================================

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
# =============================================================================
# 📖 STORIES
# =============================================================================

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

# =============================================================================
# 💬 MESSAGES DIRECTS
# =============================================================================

@dataclass
class DirectMessageSelectors:
    """Sélecteurs pour les messages directs."""
    
    # === Actions principales ===
    new_message_button: str = '//android.widget.Button[contains(@content-desc, "Nouveau message") or contains(@content-desc, "New Message")]'
    search_recipient: str = '//android.widget.EditText[contains(@text, "Rechercher") or contains(@text, "Search")]'
    message_input: str = '//android.widget.EditText[contains(@hint, "Message")]'
    send_button: str = '//android.widget.ImageButton[contains(@content-desc, "Envoyer") or contains(@content-desc, "Send")]'
    
    # === Listes et éléments ===
    thread_list: str = '//androidx.recyclerview.widget.RecyclerView[contains(@resource-id, "thread_list")]'
    thread_item: str = '//android.view.ViewGroup[contains(@resource-id, "thread_row_thread")]'

# =============================================================================
# 🪟 POPUPS & MODALES
# =============================================================================

@dataclass
class PopupSelectors:
    """Sélecteurs pour les popups et modales (likers, followers, etc.)."""
    
    # === Utilisateurs dans les popups ===
    username_in_popup_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_user_primary_name"]',
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        '//*[@resource-id="com.instagram.android:id/username"]'
    ])
    
    # === Détection des popups ===
    popup_bounds_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/bottom_sheet_container"]',
        '//*[@resource-id="com.instagram.android:id/modal_container"]',
        '//*[@resource-id="com.instagram.android:id/dialog_container"]',
        '//*[contains(@resource-id, "sheet")]',
        '//*[contains(@resource-id, "popup")]'
    ])
    
    likers_popup_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "J\'aime")]',
        '//*[contains(@text, "En commun")]',
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        '//*[@resource-id="com.instagram.android:id/row_user_primary_name"]',
        '//*[@resource-id="com.instagram.android:id/bottom_sheet_container"]'
    ])
    
    # === Sélecteurs automation.py ===
    automation_popup_indicators: List[str] = field(default_factory=lambda: [
        "//android.widget.TextView[@text='Likes']",
        "//android.widget.TextView[@text='J\'aime']",
        "//android.widget.TextView[@text='Like']",
        "//android.widget.EditText[contains(@text, 'Search') or contains(@text, 'Rechercher')]",
        "//android.widget.RecyclerView[contains(@resource-id, 'list')]",
        "//android.widget.ImageView[@content-desc='Close']",
        "//android.widget.ImageView[@content-desc='Fermer']",
        "//android.widget.Button[@text='Follow' or @text='Suivre']"
    ])
    
    automation_user_selectors: List[str] = field(default_factory=lambda: [
        "//android.widget.LinearLayout[.//android.widget.TextView and .//android.widget.Button[@text='Follow' or @text='Suivre']]",
        "//android.view.ViewGroup[.//android.widget.TextView and .//android.widget.Button[@text='Follow' or @text='Suivre']]",
        "//android.widget.LinearLayout[.//android.widget.TextView]",
        "//android.view.ViewGroup[.//android.widget.TextView]"
    ])
    
    close_popup_selectors: List[str] = field(default_factory=lambda: [
        "//android.widget.ImageView[@content-desc='Close']",
        "//android.widget.ImageView[@content-desc='Fermer']",
        "//android.widget.Button[@content-desc='Close']",
        "//android.widget.Button[@content-desc='Fermer']"
    ])
    
    username_in_user_element: str = "//android.widget.TextView[1]"
    follow_button_in_user_element: str = "//android.widget.Button[@text='Follow' or @text='Suivre']"
    
    # === Dialogs génériques ===
    dialog_selectors: Dict[str, str] = field(default_factory=lambda: {
        'dialog_title': '//android.widget.TextView[contains(@resource-id, "dialog_title")]',
        'dialog_message': '//android.widget.TextView[contains(@resource-id, "message")]',
        'dialog_positive_button': '//android.widget.Button[contains(@resource-id, "button1")]',
        'dialog_negative_button': '//android.widget.Button[contains(@resource-id, "button2")]',
        'dialog_neutral_button': '//android.widget.Button[contains(@resource-id, "button3")]',
        'toast_message': '//android.widget.Toast[1]',
        'popup_close': '//android.widget.ImageView[contains(@content-desc, "Fermer") or contains(@content-desc, "Close")]',
        'rate_app_dialog': '//android.widget.TextView[contains(@text, "Note") or contains(@text, "Rate")]',
        'update_app_dialog': '//android.widget.TextView[contains(@text, "Mise à jour") or contains(@text, "Update")]'
    })
    
    not_now_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Not Now")]',
        '//android.widget.Button[contains(@text, "Pas maintenant")]',
        '//android.widget.TextView[contains(@text, "Not Now")]',
        '//android.widget.TextView[contains(@text, "Pas maintenant")]'
    ])
    
    # === Popup de suggestions après follow ===
    follow_suggestions_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Suggested for you")]',
        '//android.widget.TextView[contains(@text, "Suggestions")]',
        '//*[contains(@resource-id, "suggested")]',
        '//*[contains(@content-desc, "Suggested")]'
    ])
    
    follow_suggestions_close_methods: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Close")]',
        '//*[contains(@content-desc, "Dismiss")]',
        '//*[contains(@text, "×")]',
        '//*[contains(@content-desc, "Fermer")]'
    ])
    
    # === Sélecteurs hashtag_business.py ===
    username_list_selector: str = '//*[@resource-id="com.instagram.android:id/follow_list_username"]'
    drag_handle_selector: str = '//*[@resource-id="com.instagram.android:id/bottom_sheet_drag_handle_prism"]'

# =============================================================================
# 📜 SCROLL & CHARGEMENT
# =============================================================================

@dataclass 
class ScrollSelectors:
    """Sélecteurs pour la détection de fin de scroll et éléments de chargement."""
    
    # === Indicateurs de chargement ===
    load_more_selectors: List[str] = field(default_factory=lambda: [
        # Sélecteurs français (Instagram France)
        "//android.widget.TextView[contains(@text, 'Voir plus')]",
        "//android.widget.Button[contains(@text, 'Voir plus')]",
        "//*[contains(@content-desc, 'Voir plus')]",
        "//android.widget.TextView[contains(@text, 'voir plus')]",
        # Sélecteurs anglais (Instagram international)
        "//android.widget.TextView[contains(@text, 'See more')]",
        "//android.widget.Button[contains(@text, 'See more')]",
        "//*[contains(@content-desc, 'See more')]",
        "//android.widget.TextView[contains(@text, 'see more')]",
        # Sélecteurs génériques (fallback)
        '//*[@text="Load more" or @text="Show more" or @text="See more"]',
        '//*[contains(@text, "Load") and contains(@text, "more")]',
        '//*[@content-desc="Load more" or @content-desc="Show more"]',
        '//android.widget.Button[contains(@text, "more")]'
    ])
    
    # === Indicateurs de fin de liste ===
    end_of_list_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/see_all_button"]',  # Bouton "See all suggestions" = fin de liste followers
        '//*[@text="See all suggestions"]',
        '//*[contains(@text, "See all suggestions")]',
        '//*[@text="You\'re all caught up" or @text="No more suggestions"]',
        '//*[contains(@text, "caught up") or contains(@text, "End of list")]',
        '//*[contains(@text, "No more") or contains(@text, "That\'s all")]'
    ])

# =============================================================================
# 🔍 DETECTION & ÉTATS D'ÉCRAN
# =============================================================================

@dataclass
class DetectionSelectors:
    """Sélecteurs pour la détection d'écrans, d'états et d'erreurs."""
    
    # === Détection d'écrans ===
    home_screen_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Accueil") and @selected="true"]',
        '//*[contains(@content-desc, "Home") and @selected="true"]',
        '//*[contains(@resource-id, "feed_timeline")]'
    ])
    
    search_screen_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Rechercher") and @selected="true"]',
        '//*[contains(@content-desc, "Search") and @selected="true"]',
        '//*[contains(@resource-id, "search_edit_text")]'
    ])
    
    profile_screen_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "profile_header")]',
        '//*[contains(@resource-id, "coordinator_root_layout")]',
        '//*[contains(@resource-id, "action_bar_title")]',
        '//*[contains(@resource-id, "profile_header_full_name")]',
        '//*[@content-desc="Modifier le profil"]',
        '//*[contains(@text, "Modifier le profil")]',
        '//*[@content-desc="Edit profile"]',
        '//*[contains(@text, "Edit profile")]',
        '//*[contains(@text, "Follow")]',
        '//*[contains(@text, "Suivre")]',
        '//*[contains(@text, "Following")]',
        '//*[contains(@text, "Abonné")]'
    ])
    
    own_profile_indicators: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Modifier le profil"]',
        '//*[contains(@text, "Modifier le profil")]',
        '//*[@content-desc="Edit profile"]',
        '//*[contains(@text, "Edit profile")]',
        '//*[contains(@text, "Partager le profil")]',
        '//*[contains(@text, "Share profile")]',
        '//*[@resource-id="com.instagram.android:id/button_container" and @content-desc="Modifier le profil"]'
    ])
    
    story_viewer_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "reel_viewer")]',
        '//*[contains(@resource-id, "story_viewer")]'
    ])
    
    post_screen_indicators: List[str] = field(default_factory=lambda: [
        # PRIORITY 1: Generic selectors (work for BOTH Reels and Posts) - CHECK FIRST
        '//*[contains(@content-desc, "Like")]',  # Works for both! Fast detection
        '//*[contains(@content-desc, "Comment")]',  # Works for both! Fast detection
        
        # PRIORITY 2: Reel-specific selectors (if generic fails)
        '//*[@resource-id="com.instagram.android:id/clips_single_media_component"]',
        '//*[@resource-id="com.instagram.android:id/like_button"]',  # Reel like button
        
        # PRIORITY 3: Regular post selectors (fallback for posts only)
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_share"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_view_group_buttons"]'
    ])
    
    # === Détection de contenu ===
    story_ring_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "story_ring")]',
        '//*[contains(@content-desc, "Story")]',
        '//*[contains(@resource-id, "reel_ring")]'
    ])
    
    # === Messages d'erreur ===
    error_message_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Erreur")]',
        '//*[contains(@text, "Error")]',
        '//*[contains(@text, "Impossible")]',
        '//*[contains(@text, "Failed")]',
        '//*[contains(@text, "Échec")]',
        '//*[contains(@text, "Retry")]',
        '//*[contains(@text, "Réessayer")]'
    ])
    
    rate_limit_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Trop de tentatives")]',
        '//*[contains(@text, "Too many requests")]',
        '//*[contains(@text, "Veuillez patienter")]',
        '//*[contains(@text, "Please wait")]',
        '//*[contains(@text, "Action bloquée")]',
        '//*[contains(@text, "Action blocked")]'
    ])
    
    login_required_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Se connecter")]',
        '//*[contains(@text, "Log in")]',
        '//*[contains(@text, "Connexion")]',
        '//*[contains(@text, "Login")]'
    ])
    
    # === Détection de popups ===
    popup_types: Dict[str, str] = field(default_factory=lambda: {
        "En commun": '//*[contains(@text, "En commun")]',
        "Mutual": '//*[contains(@text, "Mutual")]',
        "Notification": '//*[contains(@text, "Notification")]',
        "Permission": '//*[contains(@text, "Permission")]',
        "Update": '//*[contains(@text, "Mise à jour")]'
    })
    
    # === État du post (liked) ===
    liked_button_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Unlike")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Ne plus aimer")]',
        '//*[contains(@content-desc, "Unlike")]',
        '//*[contains(@content-desc, "Ne plus aimer")]'
    ])
    
    # === Navigation - Search bars ===
    search_bar_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@resource-id="com.instagram.android:id/action_bar_search_edit_text"]',
        '//android.widget.EditText[contains(@text, "Rechercher")]',
        '//android.widget.EditText[contains(@text, "Search")]',
        '//android.widget.EditText[@clickable="true"]'
    ])
    
    hashtag_search_bar_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@resource-id="com.instagram.android:id/action_bar_search_edit_text"]',
        '//android.widget.EditText[contains(@text, "Rechercher")]',
        '//android.widget.EditText[contains(@text, "Search")]',
        '//android.widget.EditText[@clickable="true"]'
    ])
    
    hashtag_page_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "publications")]',
        '//*[contains(@text, "posts")]',
        '//*[contains(@text, "Recent")]',
        '//*[contains(@text, "Top")]'
    ])
    
    # === Post errors (unavailable, private, not found) ===
    post_error_indicators: List[str] = field(default_factory=lambda: [
        # Optimized: Most common error patterns first (faster detection)
        '//*[contains(@text, "Sorry") or contains(@text, "Désolé")]',
        '//*[contains(@text, "not found") or contains(@text, "introuvable")]',
        '//*[contains(@text, "unavailable") or contains(@text, "indisponible")]',
        '//*[contains(@text, "private") or contains(@text, "privé")]'
        
        # Old approach (8 separate checks = 16s timeout if no error):
        # '//*[contains(@text, "Sorry")]',
        # '//*[contains(@text, "Désolé")]',
        # '//*[contains(@text, "not found")]',
        # '//*[contains(@text, "introuvable")]',
        # '//*[contains(@text, "unavailable")]',
        # '//*[contains(@text, "indisponible")]',
        # '//*[contains(@text, "private")]',
        # '//*[contains(@text, "privé")]'
    ])
    
    # === Followers/Following list ===
    followers_list_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "follow_list_container")]',
        '//*[contains(@resource-id, "follow_list_username")]'
    ])
    
    # === Load more / End of list ===
    load_more_selectors: List[str] = field(default_factory=lambda: [
        "//android.widget.TextView[contains(@text, 'Voir plus')]",
        "//android.widget.Button[contains(@text, 'Voir plus')]",
        "//*[contains(@content-desc, 'Voir plus')]",
        "//android.widget.TextView[contains(@text, 'voir plus')]",
        "//android.widget.TextView[contains(@text, 'See more')]",
        "//android.widget.Button[contains(@text, 'See more')]",
        "//*[contains(@content-desc, 'See more')]",
        "//android.widget.TextView[contains(@text, 'see more')]",
        '//*[@text="Load more" or @text="Show more" or @text="See more"]',
        '//*[contains(@text, "Load") and contains(@text, "more")]',
        '//*[@content-desc="Load more" or @content-desc="Show more"]',
        '//android.widget.Button[contains(@text, "more")]'
    ])
    
    end_of_list_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/see_all_button"]',  # Bouton "See all suggestions" = fin de liste followers
        '//*[@text="See all suggestions"]',
        '//*[contains(@text, "See all suggestions")]',
        '//*[@text="You\'re all caught up" or @text="No more suggestions"]',
        '//*[contains(@text, "caught up") or contains(@text, "End of list")]',
        '//*[contains(@text, "No more") or contains(@text, "That\'s all")]',
        '//*[contains(@text, "Aucun autre") or contains(@text, "Fin de")]'
    ])
    
    # === Hashtag & Grid Navigation ===
    post_grid_selector: str = '//*[@resource-id="com.instagram.android:id/image_button"]'
    
    recent_tab_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Recent"]',
        '//android.widget.TextView[@text="Récent"]',
        '//*[contains(@text, "Recent")]',
        '//*[contains(@text, "Récent")]',
        '//android.widget.TextView[contains(@content-desc, "Recent")]'
    ])
    
    # === Likes count (to open likers list) ===
    likes_count_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/like_count"]',
        '//*[contains(@content-desc, "Nombre de J\'aime")]',
        '//*[contains(@content-desc, "likes")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_like_count_facepile"]',
        '//android.widget.TextView[contains(@text, "J\'aime")]',
        '//android.widget.TextView[contains(@text, "likes")]'
    ])
    
    # === Post grid selectors (for clicking specific posts) ===
    post_grid_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[@clickable="true"]',
        '//android.widget.FrameLayout//android.widget.ImageView',
        '//android.view.ViewGroup[@clickable="true"]//android.widget.ImageView',
        '//android.widget.ImageButton[@resource-id="com.instagram.android:id/image_button"]'
    ])

# =============================================================================
# ⌨️ TEXT INPUT & FORMS
# =============================================================================

@dataclass
class TextInputSelectors:
    """Sélecteurs pour les champs de saisie de texte."""
    
    # === Comment field ===
    comment_field_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_edittext"]',
        '//*[contains(@hint, "Ajouter un commentaire")]',
        '//*[contains(@hint, "Add a comment")]',
        '//*[contains(@resource-id, "comment_edittext")]'
    ])
    
    # === Caption field ===
    caption_field_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/caption_text_view"]',
        '//*[contains(@hint, "Écrivez une légende")]',
        '//*[contains(@hint, "Write a caption")]',
        '//*[contains(@resource-id, "caption")]'
    ])
    
    # === Bio field ===
    bio_field_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/bio"]',
        '//*[contains(@hint, "Biographie")]',
        '//*[contains(@hint, "Bio")]',
        '//*[contains(@resource-id, "biography")]'
    ])
    
    # === Message field (DM) ===
    message_field_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_thread_composer_edittext"]',
        '//*[contains(@hint, "Message")]',
        '//*[contains(@hint, "Aa")]',
        '//*[contains(@resource-id, "composer_edittext")]'
    ])
    
    # === Send button (DM) ===
    send_button_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_thread_composer_button_send"]',
        '//*[contains(@content-desc, "Envoyer")]',
        '//*[contains(@content-desc, "Send")]',
        '//*[contains(@resource-id, "send")]'
    ])

# =============================================================================
# 🔧 DEBUG & UTILITAIRES
# =============================================================================

@dataclass
class DebugSelectors:
    """Sélecteurs pour le debug et l'analyse de l'interface."""
    
    # === Éléments génériques ===
    clickable_elements: str = '//*[@clickable="true"]'
    image_views: str = '//android.widget.ImageView'
    recycler_views: str = '//androidx.recyclerview.widget.RecyclerView'
    image_buttons: str = '//*[contains(@resource-id, "image_button")]'

# =============================================================================
# 🚀 INSTANCES PRÉDÉFINIES
# =============================================================================

# Instances globales pour une utilisation facile dans tous les modules
NAVIGATION_SELECTORS = NavigationSelectors()
BUTTON_SELECTORS = ButtonSelectors()
PROFILE_SELECTORS = ProfileSelectors()
POST_SELECTORS = PostSelectors()
STORY_SELECTORS = StorySelectors()
DM_SELECTORS = DirectMessageSelectors()
POPUP_SELECTORS = PopupSelectors()
SCROLL_SELECTORS = ScrollSelectors()
DETECTION_SELECTORS = DetectionSelectors()
TEXT_INPUT_SELECTORS = TextInputSelectors()
DEBUG_SELECTORS = DebugSelectors()

# =============================================================================
# 📋 RÉSUMÉ DES SÉLECTEURS DISPONIBLES
# =============================================================================

"""
Structure organisée des sélecteurs UI Instagram :

🧭 NAVIGATION_SELECTORS:
   - Navigation principale (home, search, reels, activity, profile)
   - Boutons système (back, close)
   - Onglets et navigation

👤 PROFILE_SELECTORS:
   - Informations de profil (username, bio, compteurs)
   - Boutons d'action (follow, message)
   - Détection profils privés
   - Onglets de profil

📱 POST_SELECTORS:
   - Conteneurs et métadonnées de posts
   - Extraction de likes et commentaires
   - Détection Reels vs posts classiques
   - Sélecteurs spécialisés pour automation.py
   - Boutons d'interaction (like, comment, save, share)

📖 STORY_SELECTORS:
   - Éléments de stories
   - Navigation dans les stories

💬 DM_SELECTORS:
   - Messages directs
   - Recherche et envoi

🪟 POPUP_SELECTORS:
   - Popups et modales (likers, followers)
   - Dialogs système
   - Sélecteurs spécialisés pour automation.py

📜 SCROLL_SELECTORS:
   - Détection de fin de scroll
   - Indicateurs de chargement

🔍 DETECTION_SELECTORS:
   - Détection d'écrans (home, search, profile, story viewer)
   - Détection d'états (own profile, liked post)
   - Messages d'erreur et rate limits
   - Détection de popups

🔧 DEBUG_SELECTORS:
   - Éléments pour debug et analyse

Utilisation :
from taktik.core.social_media.instagram.ui.selectors import POST_SELECTORS, DETECTION_SELECTORS
like_button = device.xpath(POST_SELECTORS.like_count_selectors[0])
is_home = device.xpath(DETECTION_SELECTORS.home_screen_indicators[0])
"""
