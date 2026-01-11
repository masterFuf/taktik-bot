"""
Sélecteurs UI pour TikTok - Organisés par fonctionnalité.

Ce module contient tous les sélecteurs d'éléments d'interface utilisateur pour TikTok,
organisés de manière logique par catégories fonctionnelles.

IMPORTANT: Tous les sélecteurs sont basés sur resource-id, content-desc ou text.
JAMAIS de bounds en dur pour garantir la compatibilité multi-résolution.

Structure:
- Navigation & Boutons système
- Profils utilisateurs  
- Vidéos (For You, Following)
- Inbox & Messages
- Popups & Modales
- Scroll & Chargement
- Détection & Debug

Package TikTok: com.zhiliaoapp.musically
Dernière mise à jour: 7 janvier 2026 (basé sur UI dumps réels)
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

# Package TikTok
TIKTOK_PACKAGE = "com.zhiliaoapp.musically"

# =============================================================================
# 🔐 AUTHENTIFICATION & LOGIN
# =============================================================================

@dataclass
class AuthSelectors:
    """Sélecteurs pour l'authentification et le login TikTok."""
    
    # === Champs de saisie (multilingue) ===
    username_field: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@content-desc, "Email or username")]',
        '//android.widget.EditText[contains(@content-desc, "E-mail ou nom d\'utilisateur")]',
        '//android.widget.EditText[contains(@content-desc, "Phone number")]',
        '//android.widget.EditText[@password="false" and @clickable="true"][1]',
        '(//android.widget.EditText)[1]'
    ])
    
    password_field: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@content-desc, "Password")]',
        '//android.widget.EditText[contains(@content-desc, "Mot de passe")]',
        '//android.widget.EditText[@password="true"]',
        '(//android.widget.EditText)[2]'
    ])
    
    # === Boutons d'action (multilingue) ===
    login_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Log in"]',
        '//android.widget.Button[@content-desc="Se connecter"]',
        '//android.widget.Button[contains(@text, "Log in")]',
        '//android.widget.Button[contains(@text, "Se connecter")]',
    ])
    
    # === Détection de la page de login ===
    login_screen_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[contains(@content-desc, "TikTok")]',
        '//*[contains(@text, "Log in")]',
        '//*[contains(@text, "Sign up")]',
    ])

# =============================================================================
# 🏠 NAVIGATION & BOTTOM BAR
# =============================================================================

@dataclass
class NavigationSelectors:
    """Sélecteurs pour la navigation principale TikTok.
    
    Basé sur UI dump: ui_dump_20260107_205804.xml (For You page)
    Resource-IDs identifiés:
    - mky: Bottom navigation container
    - mkq: Home tab
    - mkp: Friends tab
    - mkn: Create button
    - mkr: Inbox tab
    - mks: Profile tab
    """
    
    # === Bottom Navigation Bar (resource-ids réels) ===
    bottom_nav_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mky"]',
    ])
    
    home_tab: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mkq"]',
        '//android.widget.FrameLayout[@content-desc="Home"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Accueil")]',
    ])
    
    friends_tab: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mkp"]',
        '//android.widget.FrameLayout[@content-desc="Friends"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Amis")]',
    ])
    
    create_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mkn"]',
        '//android.widget.Button[@content-desc="Create"]',
        '//android.widget.Button[contains(@content-desc, "Créer")]',
    ])
    
    inbox_tab: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mkr"]',
        '//android.widget.FrameLayout[@content-desc="Inbox"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Boîte de réception")]',
        '//*[@content-desc="Inbox"]',
        '//*[contains(@content-desc, "Inbox")]',
        '//*[contains(@content-desc, "Messages")]',
    ])
    
    profile_tab: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mks"]',
        '//android.widget.FrameLayout[@content-desc="Profile"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Profil")]',
    ])
    
    # === Header Tabs (For You page) ===
    live_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="LIVE"]',
        '//*[@text="LIVE"]',
    ])
    
    explore_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Explore"]',
        '//*[@text="Explore"]',
        '//*[contains(@content-desc, "Explorer")]',
    ])
    
    following_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Following"]',
        '//*[@text="Following"]',
        '//*[contains(@content-desc, "Abonnements")]',
    ])
    
    shop_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Shop"]',
        '//*[@text="Shop"]',
        '//*[contains(@content-desc, "Boutique")]',
    ])
    
    for_you_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="For You"]',
        '//*[@text="For You"]',
        '//*[contains(@content-desc, "Pour toi")]',
    ])
    
    # === Search button (header on For You page) ===
    # Resource-id: irz (from ui_dump_20260111_121059.xml)
    search_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/irz"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/irz"][@content-desc="Search"]',
        '//android.widget.ImageView[@content-desc="Search"]',
        '//*[@content-desc="Search"][@clickable="true"]',
        '//*[contains(@content-desc, "Rechercher")][@clickable="true"]',
    ])
    
    # === Back button ===
    back_button: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageButton[@content-desc="Back"]',
        '//android.widget.ImageButton[@content-desc="Retour"]',
        '//android.widget.ImageView[@content-desc="Back"]',
        '//*[@resource-id="com.android.systemui:id/back"]',
    ])

# =============================================================================
# 👤 PROFIL UTILISATEUR
# =============================================================================

@dataclass
class ProfileSelectors:
    """Sélecteurs pour les profils utilisateurs TikTok.
    
    Basé sur UI dump: ui_dump_20260107_210156.xml (Profile page)
    Resource-IDs identifiés:
    - qf8: Display name
    - qh5: @username
    - qfw: Compteurs (following/followers/likes)
    - qfv: Labels des compteurs
    - b5s: Profile photo
    - h9p: Profile views button
    - xvy: Profile views count
    """
    
    # === Header profil ===
    profile_photo: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/b5s"]',
        '//android.widget.Button[@content-desc="Profile photo"]',
        '//*[contains(@content-desc, "Photo de profil")]',
    ])
    
    create_story_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Create a Story"]',
        '//*[contains(@content-desc, "Créer une Story")]',
    ])
    
    profile_views_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/h9p"]',
        '//android.widget.Button[@content-desc="Profile views"]',
    ])
    
    profile_views_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/xvy"]',
    ])
    
    profile_menu_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Profile menu"]',
        '//*[contains(@content-desc, "Menu du profil")]',
    ])
    
    # === Informations profil ===
    display_name: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qf8"]',
    ])
    
    username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qh5"]',
    ])
    
    edit_profile_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Edit"]',
        '//android.widget.Button[@text="Modifier"]',
        '//android.widget.Button[contains(@text, "Edit profile")]',
    ])
    
    # === Compteurs (utilise qfw pour les valeurs, qfv pour les labels) ===
    stat_value: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qfw"]',
    ])
    
    stat_label: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qfv"]',
    ])
    
    following_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qfv"][@text="Following"]/..//*[@resource-id="com.zhiliaoapp.musically:id/qfw"]',
        '//android.widget.TextView[@text="Following"]/preceding-sibling::android.widget.TextView',
    ])
    
    followers_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qfv"][@text="Followers"]/..//*[@resource-id="com.zhiliaoapp.musically:id/qfw"]',
        '//android.widget.TextView[@text="Followers"]/preceding-sibling::android.widget.TextView',
    ])
    
    likes_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qfv"][@text="Likes"]/..//*[@resource-id="com.zhiliaoapp.musically:id/qfw"]',
        '//android.widget.TextView[@text="Likes"]/preceding-sibling::android.widget.TextView',
    ])
    
    # === Bio ===
    bio: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "For ") or contains(@text, "http")]',
        '//*[contains(@text, "instagram.com") or contains(@text, "youtube.com")]',
    ])
    
    tiktok_studio_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/a_l"]',
        '//*[@text="TikTok Studio"]',
    ])
    
    # === Onglets de contenu profil ===
    videos_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Videos"]',
        '//*[contains(@content-desc, "Vidéos")]',
    ])
    
    private_videos_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Private videos"]',
        '//*[contains(@content-desc, "Vidéos privées")]',
    ])
    
    favourites_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Favourites"]',
        '//*[@content-desc="Favorites"]',
        '//*[contains(@content-desc, "Favoris")]',
    ])
    
    liked_videos_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Liked videos"]',
        '//*[contains(@content-desc, "Vidéos aimées")]',
    ])
    
    # === Grille de vidéos ===
    video_grid: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/gxd"]',
        '//android.widget.GridView',
    ])
    
    video_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/e52"]',
    ])
    
    video_cover: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/cover"]',
    ])
    
    video_view_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/xxy"]',
    ])
    
    # === Boutons d'action profil (sur profil d'un autre utilisateur) ===
    follow_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@content-desc, "Follow")]',
        '//android.widget.Button[@text="Follow"]',
        '//android.widget.Button[@text="Suivre"]',
    ])
    
    following_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Following"]',
        '//android.widget.Button[@text="Abonné"]',
        '//android.widget.Button[contains(@text, "Friends")]',
    ])
    
    message_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Message"]',
        '//android.widget.Button[@text="Message"]',
    ])

# =============================================================================
# 🎬 VIDÉOS & INTERACTIONS (For You Feed)
# =============================================================================

@dataclass
class VideoSelectors:
    """Sélecteurs pour les vidéos et interactions TikTok.
    
    Basé sur UI dump: ui_dump_20260107_205804.xml (For You page)
    Resource-IDs identifiés:
    - yx4: Profile image du créateur
    - hi1: Follow button
    - f57: Like button / Share button (même ID, différent content-desc)
    - dtv: Comment button
    - guh: Favorite button
    - nhe: Sound button
    - title: Username du créateur
    - desc: Description de la vidéo
    - f4z: Like count
    - dp9: Comment count
    - t_2: Share count
    - gtv: Favorite count
    - ru3: Ad label (publicité)
    """
    
    # === Profil créateur (côté droit, en haut) ===
    creator_profile_image: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/yx4"]',
        '//android.widget.ImageView[contains(@content-desc, "profile")]',
    ])
    
    # === Bouton Follow (sous le profil créateur) ===
    follow_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/hi1"]',
        '//android.widget.Button[contains(@content-desc, "Follow")]',
        '//*[contains(@content-desc, "Follow") and not(contains(@content-desc, "Following"))]',
    ])
    
    # === Bouton Like ===
    like_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Like video")]',
        '//android.widget.Button[contains(@content-desc, "Like video")]',
        '//*[contains(@content-desc, "Like video")]',
    ])
    
    like_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/f4z"]',
    ])
    
    # === Bouton Comment ===
    comment_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/dtv"]',
        '//android.widget.Button[contains(@content-desc, "comments")]',
        '//*[contains(@content-desc, "Read or add comments")]',
    ])
    
    comment_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/dp9"]',
    ])
    
    # === Bouton Favorite ===
    favorite_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/guh"]',
        '//android.widget.Button[contains(@content-desc, "Favourites")]',
        '//android.widget.Button[contains(@content-desc, "Favorites")]',
        '//*[contains(@content-desc, "Add or remove this video from Favourites")]',
    ])
    
    favorite_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/gtv"]',
    ])
    
    # === Bouton Share ===
    share_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Share video")]',
        '//android.widget.Button[contains(@content-desc, "Share video")]',
        '//*[contains(@content-desc, "Share video")]',
    ])
    
    share_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/t_2"]',
    ])
    
    # === Bouton Sound (disque en bas à droite) ===
    sound_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/nhe"]',
        '//android.widget.Button[contains(@content-desc, "Sound:")]',
    ])
    
    # === Informations vidéo (bas de l'écran) ===
    author_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/title"]',
    ])
    
    video_description: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/desc"]',
    ])
    
    # === Conteneur vidéo (pour double tap like) ===
    video_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/gy_"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/long_press_layout"]',
        '//android.view.View[@content-desc="Video"]',
    ])
    
    player_view: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/player_view"]',
    ])
    
    # === Détection d'état vidéo ===
    video_liked_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/f4u"][@selected="true"]',
        '//android.widget.ImageView[contains(@content-desc, "Unlike")]',
    ])
    
    video_favorited_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/gtn"][@selected="true"]',
    ])
    
    # === Détection de publicité (Ad) ===
    ad_label: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ru3"][@text="Ad"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/ru3"]',
        '//android.widget.TextView[@text="Ad"]',
        '//android.widget.TextView[@text="Sponsorisé"]',
        '//android.widget.TextView[@text="Publicité"]',
    ])
    
    # === Bouton Subscribe (publicité) ===
    subscribe_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Subscribe")]',
        '//android.widget.Button[contains(@text, "S\'abonner")]',
        '//android.widget.Button[contains(@text, "Shop now")]',
        '//android.widget.Button[contains(@text, "Learn more")]',
    ])

# =============================================================================
# 💬 COMMENTAIRES
# =============================================================================

@dataclass
class CommentSelectors:
    """Sélecteurs pour les commentaires TikTok."""
    
    comment_input: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@content-desc, "Add comment")]',
        '//android.widget.EditText[contains(@content-desc, "Ajouter un commentaire")]',
        '//android.widget.EditText[contains(@resource-id, "comment_input")]'
    ])
    
    post_comment_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@content-desc, "Post")]',
        '//android.widget.Button[contains(@content-desc, "Publier")]',
        '//android.widget.Button[contains(@resource-id, "post")]'
    ])
    
    comment_list: List[str] = field(default_factory=lambda: [
        '//androidx.recyclerview.widget.RecyclerView[contains(@resource-id, "comment_list")]',
        '//android.widget.ListView[contains(@resource-id, "comment")]'
    ])

# =============================================================================
# 🔍 RECHERCHE & DÉCOUVERTE
# =============================================================================

@dataclass
class SearchSelectors:
    """Sélecteurs pour la recherche et découverte TikTok.
    
    Basé sur UI dumps:
    - ui_dump_20260111_121059.xml (For You page with search icon)
    - ui_dump_20260111_121110.xml (Search input page)
    - ui_dump_20260111_121127.xml (Search results page)
    
    Resource-IDs identifiés:
    - giv: Search input field (EditText)
    - y61: Search button (to submit search)
    - b9c: Back button (in search page)
    - c87: Clear search field button
    - ksc: Search icon in input field
    - spd: More button (3 dots)
    """
    
    # === Search icon on For You page (header) ===
    search_icon: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[@content-desc="Search"]',
        '//*[@content-desc="Search"]',
        '//*[contains(@content-desc, "Rechercher")]',
    ])
    
    # === Search input field ===
    search_input: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/giv"]',
        '//android.widget.EditText[@resource-id="com.zhiliaoapp.musically:id/giv"]',
        '//android.widget.EditText[contains(@hint, "Search")]',
        '//android.widget.EditText[contains(@content-desc, "Search")]',
    ])
    
    # === Search submit button ===
    search_submit_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/y61"][@text="Search"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/y61"]',
        '//android.widget.Button[@text="Search"]',
        '//android.widget.Button[@text="Rechercher"]',
    ])
    
    # === Back button in search page ===
    search_back_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/b9c"]',
        '//android.widget.ImageView[@resource-id="com.zhiliaoapp.musically:id/b9c"]',
    ])
    
    # === Clear search field button ===
    clear_search_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/c87"]',
        '//android.widget.ImageView[@content-desc="Clear search field"]',
    ])
    
    # === More button (3 dots) ===
    more_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/spd"]',
        '//android.widget.ImageView[@content-desc="More"]',
    ])
    
    # Legacy selectors for compatibility
    search_bar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/giv"]',
        '//android.widget.EditText[contains(@content-desc, "Search")]',
        '//android.widget.EditText[contains(@content-desc, "Rechercher")]',
    ])
    
    search_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/y61"]',
        '//android.widget.Button[contains(@content-desc, "Search")]',
        '//android.widget.Button[contains(@content-desc, "Rechercher")]',
    ])
    
    # === Filtres de recherche (tabs on results page) ===
    top_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Top"]',
    ])
    
    users_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Users"]',
        '//android.widget.TextView[@text="Utilisateurs"]',
    ])
    
    videos_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Videos"]',
        '//android.widget.TextView[@text="Vidéos"]',
    ])
    
    photos_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Photos"]',
    ])
    
    shop_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Shop"]',
        '//android.widget.TextView[@text="Boutique"]',
    ])
    
    sounds_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Sounds"]',
        '//android.widget.TextView[@text="Sons"]',
    ])
    
    hashtags_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Hashtags"]',
    ])
    
    # === Search suggestions (trending) ===
    suggestion_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Trending")]',
        '//android.widget.TextView[contains(@text, "Trending")]',
    ])
    
    # === Search results ===
    # User result item container
    user_result_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/sh2"]',
        '//android.widget.RelativeLayout[@resource-id="com.zhiliaoapp.musically:id/sh2"]',
    ])
    
    # Username in search results
    user_result_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ye2"]',
        '//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/ye2"]',
    ])
    
    # User bio in search results
    user_result_bio: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/x8i"]',
    ])
    
    # User followers count in search results
    user_result_followers: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/xf0"]',
    ])
    
    # Follow button in search results
    user_result_follow_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdh"][@text="Follow"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdh"]',
        '//android.widget.Button[@text="Follow"]',
        '//android.widget.Button[@text="Following"]',
    ])
    
    # Video thumbnail in search results
    video_thumbnail: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/cover"]',
        '//android.widget.ImageView[@resource-id="com.zhiliaoapp.musically:id/cover"]',
    ])
    
    # Video container in search results (clickable)
    video_result_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/sq1"]',
        '//android.widget.FrameLayout[@resource-id="com.zhiliaoapp.musically:id/sq1"]',
    ])
    
    # View all button
    view_all_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/sm6"][@text="View all"]',
        '//android.widget.TextView[@text="View all"]',
    ])

# =============================================================================
# � INBOX & MESSAGES
# =============================================================================

@dataclass
class InboxSelectors:
    """Sélecteurs pour la boîte de réception et messages TikTok.
    
    Basé sur UI dump: ui_dump_20260107_210126.xml (Inbox page)
    Resource-IDs identifiés:
    - ehp: Add people button
    - j6u: Search button (inbox)
    - jlc: Activity status
    - jla: RecyclerView des messages
    - b8h: Section titles (New followers, Activity, System notifications)
    - t5a: Conversation item container
    - z05: Username in conversation
    - l35: Last message text
    - l3a: Timestamp
    - fa7: Unread badge container
    """
    
    # === Header Inbox ===
    add_people_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ehp"]',
        '//android.widget.ImageView[@content-desc="Add people"]',
    ])
    
    inbox_title: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/title"][@text="Inbox"]',
        '//*[@text="Inbox"]',
    ])
    
    activity_status: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jlc"]',
        '//*[contains(@content-desc, "Activity status")]',
    ])
    
    search_inbox_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/j6u"]',
        '//android.widget.ImageView[@content-desc="Search"]',
    ])
    
    # === Liste des messages ===
    message_list: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jla"]',
        '//androidx.recyclerview.widget.RecyclerView',
    ])
    
    # === Sections de notification ===
    section_title: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/b8h"]',
    ])
    
    new_followers_section: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/b8h"][@text="New followers"]',
        '//*[@text="New followers"]',
    ])
    
    activity_section: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/b8h"][@text="Activity"]',
        '//*[@text="Activity"]',
    ])
    
    system_notifications_section: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/b8h"][@text="System notifications"]',
        '//*[@text="System notifications"]',
    ])
    
    # === Conversations ===
    conversation_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/t5a"]',
    ])
    
    conversation_avatar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/b5h"]',
    ])
    
    conversation_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/z05"]',
    ])
    
    conversation_last_message: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/l35"]',
    ])
    
    conversation_timestamp: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/l3a"]',
    ])
    
    unread_badge: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/fa7"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/lnb"]',
    ])
    
    # === Stories row ===
    stories_row: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/tsb"]',
    ])
    
    story_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/tsi"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/jmw"]',
    ])
    
    # === Notification sections (to skip) ===
    # These are notification items, not real conversations
    notification_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/s28"]',  # Notification button container
    ])
    
    notification_subtitle: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ln_"]',  # Notification subtitle text
    ])
    
    # === Group chat indicators ===
    # Groups have member count icon (like "12" with thumbs up)
    group_member_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ujj"]',  # Group member count container
    ])


# =============================================================================
# 💬 CONVERSATION (DM) SELECTORS
# =============================================================================

@dataclass
class ConversationSelectors:
    """Sélecteurs pour les conversations DM TikTok.
    
    Basé sur UI dumps:
    - ui_dump_20260107_231514.xml (conversation simple avec @lobinho)
    - ui_dump_20260107_231534.xml (conversation de groupe "Hyper Shadic & FNF Crews")
    
    Resource-IDs identifiés:
    - lep/nmy: Back button
    - h4a: Username/Group name in header
    - k9u: Avatar in header
    - sqz: Member count for groups
    - j47: Report button
    - j1_: More options button
    - r_k: Messages RecyclerView
    - tow: Message item container
    - z05: Sender username
    - e7j: Message content container (text, sticker, GIF)
    - jay: Text message content
    - p10: Sticker/GIF image
    - l9k: Date separator
    - n9t: Date text
    - jt3: Message input container
    - ja2: Emoji/sticker button
    - rh_: Reply button (for replying to specific message)
    """
    
    # === Header ===
    back_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/lep"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/nmy"][@content-desc="Back"]',
        '//android.widget.ImageView[@content-desc="Back"]',
    ])
    
    conversation_name: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/h4a"]',  # Username or group name
    ])
    
    conversation_avatar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/k9u"]',  # Avatar in header
    ])
    
    group_member_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/sqz"]',  # "29" members text
    ])
    
    report_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/j47"][@content-desc="Report"]',
    ])
    
    more_options_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/j1_"][@content-desc="More"]',
    ])
    
    # === Profile info (for new conversations) ===
    profile_avatar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qbd"]',  # Large avatar
    ])
    
    profile_display_name: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qf7"]',  # Display name
    ])
    
    profile_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qgb"]//android.widget.TextView[contains(@text, "@")]',
    ])
    
    profile_stats: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qgb"]//android.widget.TextView[contains(@text, "following")]',
    ])
    
    # === Messages list ===
    messages_list: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/r_k"]',  # RecyclerView
    ])
    
    message_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/tow"]',  # Message container
    ])
    
    message_sender: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/z05"]',  # Sender username
    ])
    
    message_sender_avatar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/b71"]',  # Small avatar next to message
        '//*[@resource-id="com.zhiliaoapp.musically:id/b5p"]',  # Clickable avatar
    ])
    
    message_content_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/e7j"]',  # Content container
    ])
    
    message_text: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jay"]',  # Text message (IMTuxTextLayoutView)
    ])
    
    message_sticker: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/p10"]',  # Sticker/GIF image
        '//*[@resource-id="com.zhiliaoapp.musically:id/e95"][@content-desc="Stickers"]',
    ])
    
    message_gif: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/e7j"][@content-desc="GIF"]',
    ])
    
    # === Date separators ===
    date_separator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/l9k"]',  # Date container
    ])
    
    date_text: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/n9t"]',  # "Today 11:15 pm"
    ])
    
    # === Reply button (for specific message) ===
    reply_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/rh_"][@text="Reply"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/j8j"]',  # Reply container
    ])
    
    # === Quick reactions bar ===
    reactions_bar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ue"]',  # Reactions container
        '//*[@resource-id="com.zhiliaoapp.musically:id/ur"]',  # Reactions RecyclerView
    ])
    
    reaction_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/uc"]',  # Individual reaction
        '//*[@resource-id="com.zhiliaoapp.musically:id/ug"]',  # Reaction icon
    ])
    
    reaction_heart: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ug"][@content-desc="Heart"]',
    ])
    
    reaction_lol: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ug"][@content-desc="Lol"]',
    ])
    
    reaction_thumbsup: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ug"][@content-desc="ThumbsUp"]',
    ])
    
    # === Message input ===
    message_input_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/yi7"]',  # Input area container
        '//*[@resource-id="com.zhiliaoapp.musically:id/fwt"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/jt2"]',
    ])
    
    message_input_field: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jt3"]//android.widget.EditText',
        '//android.widget.EditText[@hint="Message..."]',
        '//android.widget.EditText[contains(@hint, "Message")]',
    ])
    
    emoji_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ja2"][@content-desc="Open stickers, gifs and emojis"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/ja2"]',
    ])
    
    voice_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jtf"]',  # Voice message button (groups)
        '//*[@resource-id="com.zhiliaoapp.musically:id/c8f"]',
    ])
    
    send_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jt8"]',  # Send button (appears when text entered)
        '//android.widget.Button[@content-desc="Send"]',
    ])
    
    # === Sticker suggestion (new conversation) ===
    sticker_suggestion: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/q12"]',  # Sticker suggestion container
        '//*[@resource-id="com.zhiliaoapp.musically:id/q14"]',  # "Say hi by sending a sticker"
    ])
    
    close_sticker_suggestion: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/dgd"][@content-desc="Close"]',
    ])
    
    # === Games/Cards buttons ===
    games_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/v1"][@text="Games"]',
    ])
    
    cards_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/v1"][@text="Cards"]',
    ])


# =============================================================================
# 🚨 POPUPS & MODALES
# =============================================================================

@dataclass
class PopupSelectors:
    """Sélecteurs pour les popups et modales TikTok."""
    
    # === Boutons de fermeture ===
    close_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jyh"][@content-desc="Close"]',  # Popup collections
        '//*[@resource-id="com.zhiliaoapp.musically:id/fac"]',
        '//android.widget.ImageView[@content-desc="Close"]',
        '//android.widget.ImageButton[@content-desc="Close"]',
        '//android.widget.ImageButton[@content-desc="Fermer"]',
        '//android.widget.Button[@content-desc="Close"]',
    ])
    
    dismiss_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ny9"]',  # "Not now" button
        '//android.widget.Button[@content-desc="Dismiss"]',
        '//android.widget.Button[@text="Not now"]',
        '//android.widget.Button[contains(@text, "Not now")]',
        '//android.widget.Button[contains(@text, "Pas maintenant")]',
        '//android.widget.Button[contains(@text, "Skip")]',
    ])
    
    # === Popup "Create shared collections" ===
    collections_popup: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jzb"]',  # Title text
        '//*[contains(@text, "Create shared collections")]',
        '//*[contains(@text, "collections with a friend")]',
    ])
    
    collections_not_now: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ny9"][@text="Not now"]',
        '//android.widget.Button[@text="Not now"]',
    ])
    
    collections_close: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jyh"][@content-desc="Close"]',
    ])
    
    # === Popups spécifiques ===
    age_verification_popup: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "age")]',
        '//*[contains(@text, "âge")]',
        '//*[contains(@text, "birthday")]',
    ])
    
    notification_popup: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "notification")]',
        '//*[contains(@text, "Allow")]',
        '//*[contains(@text, "Autoriser")]',
    ])
    
    # === Bannières promotionnelles (comme "Hatch a Streak Pet") ===
    promo_banner: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/faf"]',
    ])
    
    promo_close_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/fad"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/fac"][@content-desc="Close"]',
    ])
    
    invite_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/fab"]',
        '//android.widget.Button[@text="Invite"]',
    ])
    
    # === Suggestion Page (Follow back / Not interested) ===
    # This page appears in the For You feed suggesting users to follow back
    suggestion_page_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/y_k"][@text="Swipe up to skip"]',
        '//*[@text="Swipe up to skip"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjl"]',  # Not interested button
    ])
    
    suggestion_not_interested: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjl"][@text="Not interested"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjl"]',
        '//android.widget.Button[@text="Not interested"]',
    ])
    
    suggestion_follow_back: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjk"][@text="Follow back"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjk"][@text="Follow"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjk"]',
        '//android.widget.Button[@text="Follow back"]',
        '//android.widget.Button[@text="Follow"]',
    ])
    
    suggestion_close: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjr"][@content-desc="Close"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjr"]',
    ])
    
    # === Comments Section (opened accidentally during scroll) ===
    # This section appears when user clicks on the comment input area
    # Detected from ui_dump_20260107_225343.xml
    comments_section_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qx0"]',  # Comments container with emojis
        '//*[@resource-id="com.zhiliaoapp.musically:id/qx_"]',  # Message input area
        '//*[@resource-id="com.zhiliaoapp.musically:id/qx1"]',  # Emoji grid
        '//*[@resource-id="com.zhiliaoapp.musically:id/jt3"]',  # Input field container
        '//*[@resource-id="com.zhiliaoapp.musically:id/ja2"][@content-desc="Open stickers, gifs and emojis"]',
        '//android.widget.EditText[@focused="true"][contains(@hint, "Message")]',
    ])
    
    comments_close_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/dqh"][@content-desc="Close"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/dqh"]',
        '//android.widget.ImageView[@content-desc="Close"]',
    ])
    
    # Comment input area on video (to detect if visible - means we might click it)
    comment_input_area: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/xi_"][@text="Comment..."]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/dzd"]',  # Comment input container
    ])
    
    # Keyboard/EditText detection (if EditText is focused, comments section is likely open)
    keyboard_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@focused="true"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/jt3"]//android.widget.EditText',
    ])

# =============================================================================
# 🔄 SCROLL & CHARGEMENT
# =============================================================================

@dataclass
class ScrollSelectors:
    """Sélecteurs pour le scroll et le chargement TikTok."""
    
    loading_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.ProgressBar',
        '//android.view.View[contains(@content-desc, "Loading")]'
    ])
    
    end_of_list: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "No more")]',
        '//android.widget.TextView[contains(@text, "Plus de")]'
    ])

# =============================================================================
# 🎯 DÉTECTION & DEBUG
# =============================================================================

@dataclass
class DetectionSelectors:
    """Sélecteurs pour la détection d'états et debug TikTok."""
    
    # === Détection de pages problématiques ===
    error_message: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "error")]',
        '//android.widget.TextView[contains(@text, "erreur")]',
        '//android.widget.TextView[contains(@text, "Something went wrong")]'
    ])
    
    network_error: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "network")]',
        '//android.widget.TextView[contains(@text, "réseau")]',
        '//android.widget.TextView[contains(@text, "No internet")]'
    ])
    
    # === Détection de restrictions ===
    rate_limit: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "too many")]',
        '//android.widget.TextView[contains(@text, "trop de")]',
        '//android.widget.TextView[contains(@text, "Try again later")]'
    ])

# =============================================================================
# 👥 FOLLOWERS LIST (pour workflow Search Followers)
# =============================================================================

@dataclass
class FollowersSelectors:
    """Sélecteurs pour la liste des followers d'un utilisateur TikTok.
    
    Basé sur UI dumps:
    - ui_dump_20260111_135605.xml (Search results - Users tab)
    - ui_dump_20260111_135614.xml (User profile page)
    - ui_dump_20260111_135622.xml (Followers list page)
    
    Resource-IDs identifiés:
    - qh5: @username on profile
    - qfw: Counter value (followers, following, likes)
    - qfv: Counter label (Followers, Following, Likes)
    - yhq: Display name in followers list
    - ygv: Username in followers list
    - rdh: Follow button in followers list
    - s6p: RecyclerView for followers list
    """
    
    # === Users tab in search results ===
    users_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Users"]',
        '//android.widget.FrameLayout[@content-desc="Users"]',
        '//android.widget.TextView[@text="Users"]',
        '//android.widget.TextView[@text="Utilisateurs"]',
    ])
    
    # === User item in search results (clickable to go to profile) ===
    # Structure: Button[@clickable] > RelativeLayout[@resource-id="sh2"] > username/displayname/followers
    user_search_item: List[str] = field(default_factory=lambda: [
        # Button containing user info (sh2 RelativeLayout)
        '//android.widget.Button[@clickable="true"][.//android.widget.RelativeLayout[@resource-id="com.zhiliaoapp.musically:id/sh2"]]',
        # Button containing username (ye2)
        '//android.widget.Button[@clickable="true"][.//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/ye2"]]',
        # Button containing Follow button (rdh)
        '//android.widget.Button[@clickable="true"][.//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/rdh"]]',
    ])
    
    # First user in search results (Users tab)
    first_user_result: List[str] = field(default_factory=lambda: [
        # First Button in RecyclerView containing user info
        '(//androidx.recyclerview.widget.RecyclerView[@resource-id="com.zhiliaoapp.musically:id/lnp"]//android.widget.Button[@clickable="true"])[1]',
        # First Button containing sh2 RelativeLayout
        '(//android.widget.Button[@clickable="true"][.//android.widget.RelativeLayout[@resource-id="com.zhiliaoapp.musically:id/sh2"]])[1]',
        # First Button containing username ye2
        '(//android.widget.Button[@clickable="true"][.//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/ye2"]])[1]',
        # Fallback: click on sh2 RelativeLayout directly (also clickable)
        '(//android.widget.RelativeLayout[@resource-id="com.zhiliaoapp.musically:id/sh2"][@clickable="true"])[1]',
    ])
    
    # === Profile page elements ===
    # Username on profile (@username)
    profile_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qh5"]',
        '//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/qh5"]',
    ])
    
    # Followers counter (clickable to open followers list)
    followers_counter: List[str] = field(default_factory=lambda: [
        '//android.view.ViewGroup[@clickable="true"][.//android.widget.TextView[@text="Followers"]]',
        '//android.view.ViewGroup[@clickable="true"][.//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/qfv"][@text="Followers"]]',
        '//*[.//android.widget.TextView[@text="Followers"]][@clickable="true"]',
    ])
    
    # Following counter
    following_counter: List[str] = field(default_factory=lambda: [
        '//android.widget.LinearLayout[@clickable="true"][.//android.widget.TextView[@text="Following"]]',
        '//*[.//android.widget.TextView[@text="Following"]][@clickable="true"]',
    ])
    
    # Follow button on profile
    profile_follow_button: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/eme"][@text="Follow"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/eme"][@text="Follow"]',
    ])
    
    # === Followers list page ===
    # Followers tab in profile tabs
    followers_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Followers")]',
        '//*[contains(@text, "Followers")][@clickable="true"]',
    ])
    
    # Following tab in profile tabs
    following_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Following")][@selected="false"]',
    ])
    
    # RecyclerView containing followers list
    followers_list: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/s6p"]',
        '//androidx.recyclerview.widget.RecyclerView[@resource-id="com.zhiliaoapp.musically:id/s6p"]',
    ])
    
    # Individual follower item (clickable row)
    follower_item: List[str] = field(default_factory=lambda: [
        '//android.widget.LinearLayout[@clickable="true"][.//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/rdh"]]',
    ])
    
    # Display name in followers list
    follower_display_name: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/yhq"]',
        '//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/yhq"]',
    ])
    
    # Username in followers list
    follower_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ygv"]',
        '//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/ygv"]',
    ])
    
    # Follow button in followers list (can be "Follow", "Following", or "Friends")
    follower_follow_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdh"][@text="Follow"]',
        '//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/rdh"][@text="Follow"]',
    ])
    
    # Already following button
    follower_following_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdh"][@text="Following"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdh"][@text="Friends"]',
    ])
    
    # Any follow button (Follow, Following, or Friends)
    follower_any_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdh"]',
        '//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/rdh"]',
    ])
    
    # Private account notice
    private_notice: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ikr"]',
        '//android.widget.TextView[contains(@text, "can see all followers")]',
    ])
    
    # === Profile page - Video grid ===
    # GridView containing posts
    profile_grid: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/gxd"]',
        '//android.widget.GridView[@resource-id="com.zhiliaoapp.musically:id/gxd"]',
    ])
    
    # Post item in grid (clickable)
    profile_post_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/e52"][@clickable="true"]',
        '//android.widget.FrameLayout[@resource-id="com.zhiliaoapp.musically:id/e52"][@clickable="true"]',
    ])
    
    # First post in grid
    first_post: List[str] = field(default_factory=lambda: [
        '(//*[@resource-id="com.zhiliaoapp.musically:id/e52"][@clickable="true"])[1]',
        '(//android.widget.FrameLayout[@resource-id="com.zhiliaoapp.musically:id/e52"])[1]',
    ])
    
    # Post cover image
    post_cover: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/cover"]',
    ])
    
    # Post view count
    post_view_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/xxy"]',
    ])
    
    # Videos tab on profile
    profile_videos_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Videos"]',
        '//android.widget.RelativeLayout[@content-desc="Videos"]',
    ])
    
    # Reposted tab on profile
    profile_reposted_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Reposted videos"]',
        '//android.widget.RelativeLayout[@content-desc="Reposted videos"]',
    ])
    
    # === Back button (in-app) ===
    back_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/b9b"]',
        '//android.widget.ImageView[@resource-id="com.zhiliaoapp.musically:id/b9b"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/b9c"]',
    ])

# =============================================================================
# 📦 INSTANCES GLOBALES
# =============================================================================

AUTH_SELECTORS = AuthSelectors()
NAVIGATION_SELECTORS = NavigationSelectors()
PROFILE_SELECTORS = ProfileSelectors()
VIDEO_SELECTORS = VideoSelectors()
COMMENT_SELECTORS = CommentSelectors()
SEARCH_SELECTORS = SearchSelectors()
INBOX_SELECTORS = InboxSelectors()
CONVERSATION_SELECTORS = ConversationSelectors()
POPUP_SELECTORS = PopupSelectors()
SCROLL_SELECTORS = ScrollSelectors()
DETECTION_SELECTORS = DetectionSelectors()
FOLLOWERS_SELECTORS = FollowersSelectors()

# Export pour faciliter les imports
__all__ = [
    'TIKTOK_PACKAGE',
    'AuthSelectors',
    'NavigationSelectors',
    'ProfileSelectors',
    'VideoSelectors',
    'InboxSelectors',
    'ConversationSelectors',
    'CommentSelectors',
    'SearchSelectors',
    'PopupSelectors',
    'ScrollSelectors',
    'DetectionSelectors',
    'FollowersSelectors',
    'AUTH_SELECTORS',
    'NAVIGATION_SELECTORS',
    'PROFILE_SELECTORS',
    'VIDEO_SELECTORS',
    'COMMENT_SELECTORS',
    'SEARCH_SELECTORS',
    'INBOX_SELECTORS',
    'CONVERSATION_SELECTORS',
    'POPUP_SELECTORS',
    'SCROLL_SELECTORS',
    'DETECTION_SELECTORS',
    'FOLLOWERS_SELECTORS',
]
