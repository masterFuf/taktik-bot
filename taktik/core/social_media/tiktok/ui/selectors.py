"""
Sélecteurs UI pour TikTok - Organisés par fonctionnalité.

Ce module contient tous les sélecteurs d'éléments d'interface utilisateur pour TikTok,
organisés de manière logique par catégories fonctionnelles.

Structure:
- Navigation & Boutons système
- Profils utilisateurs  
- Vidéos (For You, Following)
- Lives
- Messages directs
- Popups & Modales
- Scroll & Chargement
- Debug & Utilitaires
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

# =============================================================================
# 🔐 AUTHENTIFICATION & LOGIN
# =============================================================================

@dataclass
class AuthSelectors:
    """Sélecteurs pour l'authentification et le login TikTok."""
    
    # === Champs de saisie (multilingue) ===
    username_field: List[str] = field(default_factory=lambda: [
        # Sélecteur par content-desc (anglais)
        '//android.widget.EditText[contains(@content-desc, "Email or username")]',
        # Sélecteur par content-desc (français)
        '//android.widget.EditText[contains(@content-desc, "E-mail ou nom d\'utilisateur")]',
        # Sélecteur générique par classe
        '//android.widget.EditText[@password="false" and @clickable="true"][1]',
        # Fallback par position (premier EditText)
        '(//android.widget.EditText)[1]'
    ])
    
    password_field: List[str] = field(default_factory=lambda: [
        # Sélecteur par content-desc (anglais)
        '//android.widget.EditText[contains(@content-desc, "Password")]',
        # Sélecteur par content-desc (français)
        '//android.widget.EditText[contains(@content-desc, "Mot de passe")]',
        # Sélecteur par attribut password
        '//android.widget.EditText[@password="true"]',
        # Fallback par position (second EditText)
        '(//android.widget.EditText)[2]'
    ])
    
    # === Boutons d'action (multilingue) ===
    login_button: List[str] = field(default_factory=lambda: [
        # Sélecteur par content-desc (anglais)
        '//android.widget.Button[@content-desc="Log in"]',
        # Sélecteur par content-desc (français)
        '//android.widget.Button[@content-desc="Se connecter"]',
        # Sélecteur par texte visible
        '//android.widget.Button[contains(@text, "Log in") or contains(@text, "Se connecter")]',
        # Fallback générique
        '(//android.widget.Button[@clickable="true"])[1]'
    ])
    
    # === Détection de la page de login ===
    login_screen_indicators: List[str] = field(default_factory=lambda: [
        # Logo TikTok
        '//android.widget.ImageView[contains(@content-desc, "TikTok")]',
        # Présence des champs username et password
        '//android.widget.EditText[@password="false"]/following-sibling::*//android.widget.EditText[@password="true"]'
    ])

# =============================================================================
# 🏠 NAVIGATION & BOTTOM BAR
# =============================================================================

@dataclass
class NavigationSelectors:
    """Sélecteurs pour la navigation principale TikTok."""
    
    # === Bottom Navigation Bar ===
    home_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.FrameLayout[@content-desc="Home"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Accueil")]',
        '(//android.widget.FrameLayout[@clickable="true"])[1]'
    ])
    
    discover_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.FrameLayout[@content-desc="Discover"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Découvrir")]',
        '(//android.widget.FrameLayout[@clickable="true"])[2]'
    ])
    
    create_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.FrameLayout[@content-desc="Create"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Créer")]',
        '(//android.widget.FrameLayout[@clickable="true"])[3]'
    ])
    
    inbox_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.FrameLayout[@content-desc="Inbox"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Boîte de réception")]',
        '(//android.widget.FrameLayout[@clickable="true"])[4]'
    ])
    
    profile_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.FrameLayout[@content-desc="Profile"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Profil")]',
        '(//android.widget.FrameLayout[@clickable="true"])[5]'
    ])
    
    # === Back button ===
    back_button: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageButton[@content-desc="Back"]',
        '//android.widget.ImageButton[@content-desc="Retour"]',
        '//android.widget.ImageButton[contains(@content-desc, "Navigate up")]'
    ])

# =============================================================================
# 👤 PROFIL UTILISATEUR
# =============================================================================

@dataclass
class ProfileSelectors:
    """Sélecteurs pour les profils utilisateurs TikTok."""
    
    # === Boutons d'action profil ===
    follow_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Follow"]',
        '//android.widget.Button[@content-desc="Suivre"]',
        '//android.widget.Button[contains(@text, "Follow") or contains(@text, "Suivre")]'
    ])
    
    following_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Following"]',
        '//android.widget.Button[@content-desc="Abonné"]',
        '//android.widget.Button[contains(@text, "Following") or contains(@text, "Abonné")]'
    ])
    
    message_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Message"]',
        '//android.widget.Button[@content-desc="Message"]',
        '//android.widget.Button[contains(@text, "Message")]'
    ])
    
    # === Informations profil ===
    username: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, "username")]',
        '(//android.widget.TextView)[1]'
    ])
    
    bio: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, "bio")]',
        '//android.widget.TextView[contains(@resource-id, "desc")]'
    ])
    
    followers_count: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@content-desc, "Followers")]',
        '//android.widget.TextView[contains(@content-desc, "Abonnés")]'
    ])
    
    following_count: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@content-desc, "Following")]',
        '//android.widget.TextView[contains(@content-desc, "Abonnements")]'
    ])
    
    likes_count: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@content-desc, "Likes")]',
        '//android.widget.TextView[contains(@content-desc, "J\'aime")]'
    ])

# =============================================================================
# 🎬 VIDÉOS & INTERACTIONS
# =============================================================================

@dataclass
class VideoSelectors:
    """Sélecteurs pour les vidéos et interactions TikTok."""
    
    # === Boutons d'interaction vidéo (côté droit) ===
    like_button: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[contains(@content-desc, "Like")]',
        '//android.widget.ImageView[contains(@content-desc, "J\'aime")]',
        '//android.widget.ImageView[contains(@resource-id, "like")]'
    ])
    
    comment_button: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[contains(@content-desc, "Comment")]',
        '//android.widget.ImageView[contains(@content-desc, "Commenter")]',
        '//android.widget.ImageView[contains(@resource-id, "comment")]'
    ])
    
    share_button: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[contains(@content-desc, "Share")]',
        '//android.widget.ImageView[contains(@content-desc, "Partager")]',
        '//android.widget.ImageView[contains(@resource-id, "share")]'
    ])
    
    favorite_button: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[contains(@content-desc, "Favorite")]',
        '//android.widget.ImageView[contains(@content-desc, "Favoris")]',
        '//android.widget.ImageView[contains(@resource-id, "favorite")]'
    ])
    
    # === Informations vidéo ===
    author_username: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, "author")]',
        '//android.widget.TextView[contains(@resource-id, "username")]'
    ])
    
    video_description: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, "desc")]',
        '//android.widget.TextView[contains(@resource-id, "description")]'
    ])
    
    # === Conteneur vidéo ===
    video_container: List[str] = field(default_factory=lambda: [
        '//android.view.ViewGroup[contains(@resource-id, "video")]',
        '//android.widget.FrameLayout[contains(@resource-id, "video")]'
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
    """Sélecteurs pour la recherche et découverte TikTok."""
    
    search_bar: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@content-desc, "Search")]',
        '//android.widget.EditText[contains(@content-desc, "Rechercher")]',
        '//android.widget.EditText[contains(@resource-id, "search")]'
    ])
    
    search_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@content-desc, "Search")]',
        '//android.widget.Button[contains(@content-desc, "Rechercher")]'
    ])
    
    # === Filtres de recherche ===
    users_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Users" or @text="Utilisateurs"]'
    ])
    
    videos_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Videos" or @text="Vidéos"]'
    ])
    
    hashtags_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Hashtags"]'
    ])
    
    sounds_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Sounds" or @text="Sons"]'
    ])

# =============================================================================
# 🚨 POPUPS & MODALES
# =============================================================================

@dataclass
class PopupSelectors:
    """Sélecteurs pour les popups et modales TikTok."""
    
    # === Boutons de fermeture ===
    close_button: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageButton[@content-desc="Close"]',
        '//android.widget.ImageButton[@content-desc="Fermer"]',
        '//android.widget.Button[@content-desc="Close"]',
        '//android.widget.Button[contains(@text, "Close") or contains(@text, "Fermer")]'
    ])
    
    dismiss_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Dismiss"]',
        '//android.widget.Button[contains(@text, "Not now")]',
        '//android.widget.Button[contains(@text, "Pas maintenant")]'
    ])
    
    # === Popups spécifiques ===
    age_verification_popup: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "age")]',
        '//android.widget.TextView[contains(@text, "âge")]'
    ])
    
    notification_popup: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "notification")]',
        '//android.widget.TextView[contains(@text, "Allow")]'
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
# 📦 INSTANCES GLOBALES
# =============================================================================

AUTH_SELECTORS = AuthSelectors()
NAVIGATION_SELECTORS = NavigationSelectors()
PROFILE_SELECTORS = ProfileSelectors()
VIDEO_SELECTORS = VideoSelectors()
COMMENT_SELECTORS = CommentSelectors()
SEARCH_SELECTORS = SearchSelectors()
POPUP_SELECTORS = PopupSelectors()
SCROLL_SELECTORS = ScrollSelectors()
DETECTION_SELECTORS = DetectionSelectors()

# Export pour faciliter les imports
__all__ = [
    'AuthSelectors',
    'NavigationSelectors',
    'ProfileSelectors',
    'VideoSelectors',
    'CommentSelectors',
    'SearchSelectors',
    'PopupSelectors',
    'ScrollSelectors',
    'DetectionSelectors',
    'AUTH_SELECTORS',
    'NAVIGATION_SELECTORS',
    'PROFILE_SELECTORS',
    'VIDEO_SELECTORS',
    'COMMENT_SELECTORS',
    'SEARCH_SELECTORS',
    'POPUP_SELECTORS',
    'SCROLL_SELECTORS',
    'DETECTION_SELECTORS'
]
