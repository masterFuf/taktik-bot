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
# 🔐 AUTHENTIFICATION & LOGIN
# =============================================================================

@dataclass
class AuthSelectors:
    """Sélecteurs pour l'authentification et le login Instagram."""
    
    # === Champs de saisie (multilingue) ===
    username_field: List[str] = field(default_factory=lambda: [
        # Sélecteur par content-desc (anglais)
        '//android.widget.EditText[contains(@content-desc, "Username, email or mobile number")]',
        # Sélecteur par content-desc (français)
        '//android.widget.EditText[contains(@content-desc, "Nom de profil, e-mail ou numéro de mobile")]',
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
        # Sélecteur par texte visible (anglais)
        '//android.widget.Button[.//android.view.View[@content-desc="Log in"]]',
        # Sélecteur par texte visible (français)
        '//android.widget.Button[.//android.view.View[@content-desc="Se connecter"]]',
        # Fallback générique (premier bouton cliquable après les champs)
        '(//android.widget.Button[@clickable="true"])[1]'
    ])
    
    create_account_button: List[str] = field(default_factory=lambda: [
        # Sélecteur par content-desc (anglais)
        '//android.widget.Button[@content-desc="Create new account"]',
        # Sélecteur par content-desc (français)
        '//android.widget.Button[@content-desc="Créer un compte"]',
        # Sélecteur par texte visible (anglais)
        '//android.widget.Button[.//android.view.View[@content-desc="Create new account"]]',
        # Sélecteur par texte visible (français)
        '//android.widget.Button[.//android.view.View[@content-desc="Créer un compte"]]'
    ])
    
    forgot_password_button: List[str] = field(default_factory=lambda: [
        # Sélecteur par content-desc (anglais)
        '//android.widget.Button[@content-desc="Forgot password?"]',
        # Sélecteur par content-desc (français)
        '//android.widget.Button[@content-desc="Mot de passe oublié ?"]',
        # Sélecteur par texte visible (anglais)
        '//android.widget.Button[.//android.view.View[@content-desc="Forgot password?"]]',
        # Sélecteur par texte visible (français)
        '//android.widget.Button[.//android.view.View[@content-desc="Mot de passe oublié ?"]]'
    ])
    
    # === Détection de la page de login ===
    login_screen_indicators: List[str] = field(default_factory=lambda: [
        # Logo Instagram
        '//android.widget.ImageView[@content-desc="Instagram from Meta"]',
        # Sélecteur de langue
        '//android.widget.Button[contains(@content-desc, "English") or contains(@content-desc, "Français")]',
        # Présence simultanée des champs username et password
        '//android.widget.EditText[@password="false"]/following-sibling::*//android.widget.EditText[@password="true"]'
    ])
    
    # === Écran de sélection de profil (comptes enregistrés) ===
    profile_selection_screen: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Use another profile"]',
        '//android.widget.Button[@content-desc="Utiliser un autre profil"]',
        '//android.widget.Button[@content-desc="Create new account"]',
        '//android.widget.Button[@content-desc="Créer un compte"]',
        '//*[contains(@text, "Use another profile")]',
        '//*[contains(@text, "Utiliser un autre profil")]'
    ])
    
    # === Messages d'erreur et états ===
    error_message_selectors: List[str] = field(default_factory=lambda: [
        # Messages d'erreur génériques
        '//android.widget.TextView[contains(@text, "incorrect")]',
        '//android.widget.TextView[contains(@text, "Incorrect")]',
        '//android.widget.TextView[contains(@text, "incorrecte")]',
        '//android.widget.TextView[contains(@text, "Incorrecte")]',
        # Compte bloqué/suspendu
        '//android.widget.TextView[contains(@text, "suspended")]',
        '//android.widget.TextView[contains(@text, "blocked")]',
        '//android.widget.TextView[contains(@text, "suspendu")]',
        '//android.widget.TextView[contains(@text, "bloqué")]',
        # Trop de tentatives
        '//android.widget.TextView[contains(@text, "too many")]',
        '//android.widget.TextView[contains(@text, "trop de")]',
        '//android.widget.TextView[contains(@text, "Try again")]',
        '//android.widget.TextView[contains(@text, "Réessayer")]'
    ])
    
    # === 2FA et vérification ===
    two_factor_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "security code")]',
        '//android.widget.TextView[contains(@text, "code de sécurité")]',
        '//android.widget.TextView[contains(@text, "verification")]',
        '//android.widget.TextView[contains(@text, "vérification")]',
        '//android.widget.EditText[contains(@hint, "code")]'
    ])
    
    two_factor_code_field: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "code")]',
        '//android.widget.EditText[contains(@hint, "Code")]',
        '(//android.widget.EditText)[1]'
    ])
    
    two_factor_confirm_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Confirm")]',
        '//android.widget.Button[contains(@text, "Confirmer")]',
        '//android.widget.Button[contains(@text, "Next")]',
        '//android.widget.Button[contains(@text, "Suivant")]'
    ])
    
    # === Suspicious login / Vérification supplémentaire ===
    suspicious_login_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "We detected")]',
        '//android.widget.TextView[contains(@text, "Nous avons détecté")]',
        '//android.widget.TextView[contains(@text, "unusual")]',
        '//android.widget.TextView[contains(@text, "inhabituel")]',
        '//android.widget.TextView[contains(@text, "verify")]',
        '//android.widget.TextView[contains(@text, "vérifier")]'
    ])
    
    # === Popups post-login (Save login info, Turn on notifications, etc.) ===
    save_login_info_popup: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Save Your Login Info")]',
        '//android.widget.TextView[contains(@text, "Enregistrer vos informations")]',
        '//android.widget.Button[contains(@text, "Save")]',
        '//android.widget.Button[contains(@text, "Enregistrer")]',
        '//android.widget.Button[contains(@text, "Not Now")]',
        '//android.widget.Button[contains(@text, "Pas maintenant")]'
    ])
    
    notification_popup: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Turn on Notifications")]',
        '//android.widget.TextView[contains(@text, "Activer les notifications")]',
        '//android.widget.Button[contains(@text, "Turn On")]',
        '//android.widget.Button[contains(@text, "Activer")]',
        '//android.widget.Button[contains(@text, "Not Now")]',
        '//android.widget.Button[contains(@text, "Pas maintenant")]'
    ])
    
    # === Popup contacts (Find friends) ===
    contacts_sync_popup: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Autorisez l\'accès à vos contacts")]',
        '//*[contains(@text, "Allow access to your contacts")]',
        '//*[contains(@text, "Find friends")]',
        '//*[contains(@text, "Trouver des amis")]',
        '//android.widget.Button[@content-desc="Autoriser"]',
        '//android.widget.Button[@content-desc="Allow"]',
        '//android.widget.Button[@content-desc="Ignorer"]',
        '//android.widget.Button[@content-desc="Skip"]'
    ])
    
    # === Popup localisation (Location services) ===
    location_services_popup: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Pour utiliser les Services de localisation")]',
        '//*[contains(@text, "To use Location Services")]',
        '//*[contains(@text, "Services de localisation")]',
        '//*[contains(@text, "Location Services")]',
        '//android.widget.Button[@content-desc="Continuer"]',
        '//android.widget.Button[@content-desc="Continue"]'
    ])
    
    # === Permission système localisation (Android system dialog) ===
    location_permission_dialog: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Permettre à Instagram d\'accéder à la position")]',
        '//*[contains(@text, "Allow Instagram to access this device\'s location")]',
        '//android.widget.Button[@resource-id="com.android.packageinstaller:id/permission_allow_button"]',
        '//android.widget.Button[@resource-id="com.android.packageinstaller:id/permission_deny_button"]',
        '//android.widget.Button[@text="AUTORISER"]',
        '//android.widget.Button[@text="ALLOW"]',
        '//android.widget.Button[@text="REFUSER"]',
        '//android.widget.Button[@text="DENY"]'
    ])
    
    # === Boutons génériques pour popups ===
    save_button_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Save"]',
        '//android.widget.Button[@content-desc="Enregistrer"]',
        '//android.widget.Button[contains(@text, "Save")]',
        '//android.widget.Button[contains(@text, "Enregistrer")]'
    ])
    
    skip_button_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Ignorer"]',
        '//android.widget.Button[@content-desc="Skip"]',
        '//android.widget.Button[contains(@text, "Ignorer")]',
        '//android.widget.Button[contains(@text, "Skip")]'
    ])
    
    continue_button_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Continuer"]',
        '//android.widget.Button[@content-desc="Continue"]',
        '//android.widget.Button[contains(@text, "Continuer")]',
        '//android.widget.Button[contains(@text, "Continue")]'
    ])
    
    deny_button_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@resource-id="com.android.packageinstaller:id/permission_deny_button"]',
        '//android.widget.Button[@text="REFUSER"]',
        '//android.widget.Button[@text="DENY"]'
    ])
    
    # === Détection de connexion réussie ===
    login_success_indicators: List[str] = field(default_factory=lambda: [
        # Navigation bar visible (home, search, etc.)
        '//*[contains(@content-desc, "Home") or contains(@content-desc, "Accueil")]',
        '//*[contains(@content-desc, "Search") or contains(@content-desc, "Rechercher")]',
        # Feed timeline
        '//*[@resource-id="com.instagram.android:id/feed_timeline"]',
        # Profile tab accessible
        '//*[contains(@resource-id, "profile_tab")]'
    ])

# =============================================================================
# 🧭 NAVIGATION & BOUTONS SYSTÈME
# =============================================================================

@dataclass
class NavigationSelectors:
    """Sélecteurs pour la navigation et les boutons système."""
    
    # === Navigation principale (listes pour fallbacks) ===
    # Use resource-id selectors first to avoid clicking Android system buttons
    home_tab: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "com.instagram.android:id/feed_tab")]',
        '//*[contains(@content-desc, "Accueil")]',
        '//*[contains(@content-desc, "Home")]'
    ])
    
    search_tab: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "com.instagram.android:id/search_tab")]',
        '//*[contains(@content-desc, "Rechercher")]',
        '//*[contains(@content-desc, "Search")]'
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
    
    # === Boutons de retour Instagram (complet, FR+EN) ===
    back_buttons: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_button_back"]',
        '//android.widget.ImageView[@content-desc="Retour"]',
        '//android.widget.ImageView[@content-desc="Back"]',
        '//*[@content-desc="Retour"]',
        '//*[@content-desc="Back"]',
        '//*[@content-desc="Précédent"]',
    ])
    
    # === Boutons de retour pour la liste followers/following ===
    back_buttons_action_bar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/left_action_bar_buttons"]//android.widget.ImageView[@clickable="true"]',
        '//*[@resource-id="com.instagram.android:id/left_action_bar_buttons"]/android.widget.ImageView',
        '//*[@resource-id="com.instagram.android:id/action_bar_button_back"]',
    ])
    
    # === Onglets de profil ===
    posts_tab_options: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Posts"]',
        '//*[@text="Posts"]',
        '//*[@resource-id="com.instagram.android:id/profile_tab_layout"]//android.widget.ImageView[1]',
        '//android.widget.ImageView[@content-desc="Grid view"]'
    ])
    
    # === Hashtag navigation ===
    recent_tab_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Récents")]',
        '//*[contains(@text, "Recent")]',
        '//*[contains(@content-desc, "Récents")]',
        '//*[contains(@content-desc, "Recent")]'
    ])
    
    top_tab_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Top")]',
        '//*[contains(@text, "Populaires")]',
        '//*[contains(@content-desc, "Top")]'
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
        '//*[@resource-id="com.instagram.android:id/action_bar_large_title_auto_size"]',
        '//*[@resource-id="com.instagram.android:id/action_bar_title"]',
        '//*[contains(@resource-id, "action_bar_title")]',
        '//*[contains(@resource-id, "action_bar_large_title_auto_size")]',
        '//*[contains(@resource-id, "row_profile_header_username")]',
        '//android.widget.TextView[contains(@text, "@")]'
    ])
    
    # === Username from content-desc ===
    username_content_desc: str = '//*[contains(@content-desc, "@")]'
    
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
    
    # === Liens followers/following (pour navigation) ===
    followers_link: List[str] = field(default_factory=lambda: [
        # NEW Instagram UI (2024+) - clickable container with stacked layout
        '//*[@resource-id="com.instagram.android:id/profile_header_followers_stacked_familiar"]',
        # Content-desc selectors (most reliable - works on clickable containers)
        '//*[contains(@content-desc, "followers") or contains(@content-desc, "abonnés")]',
        '//*[contains(@content-desc, "Followers") or contains(@content-desc, "Abonnés")]',
        # Resource ID selectors (various Instagram versions)
        '//*[@resource-id="com.instagram.android:id/row_profile_header_followers_container"]',
        '//*[@resource-id="com.instagram.android:id/row_profile_header_textview_followers_count"]',
        # Clickable container with followers text (parent of TextView)
        '//android.view.ViewGroup[.//android.widget.TextView[contains(@text, "followers") or contains(@text, "abonnés")]]',
        '//android.widget.LinearLayout[.//android.widget.TextView[contains(@text, "followers") or contains(@text, "abonnés")]]',
        # Text-based selectors (EN/FR) - LAST because TextView may not be clickable
        '//android.widget.TextView[contains(@text, "followers") or contains(@text, "abonnés")]',
        '//android.widget.TextView[contains(@text, "Followers") or contains(@text, "Abonnés")]'
    ])
    
    following_link: List[str] = field(default_factory=lambda: [
        # NEW Instagram UI (2024+) - clickable container with stacked layout
        '//*[@resource-id="com.instagram.android:id/profile_header_following_stacked_familiar"]',
        # Content-desc selectors (most reliable - works on clickable containers)
        '//*[contains(@content-desc, "following") or contains(@content-desc, "abonnements")]',
        '//*[contains(@content-desc, "Following") or contains(@content-desc, "Abonnements")]',
        # Resource ID selectors
        '//*[@resource-id="com.instagram.android:id/row_profile_header_following_container"]',
        '//*[@resource-id="com.instagram.android:id/row_profile_header_textview_following_count"]',
        # Clickable container with following text (parent of TextView)
        '//android.view.ViewGroup[.//android.widget.TextView[contains(@text, "following") or contains(@text, "abonnements")]]',
        '//android.widget.LinearLayout[.//android.widget.TextView[contains(@text, "following") or contains(@text, "abonnements")]]',
        # Text-based selectors (EN/FR) - LAST because TextView may not be clickable
        '//android.widget.TextView[contains(@text, "following") or contains(@text, "abonnements")]',
        '//android.widget.TextView[contains(@text, "Following") or contains(@text, "Abonnements")]'
    ])
    
    # === Full name ===
    full_name: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_header_full_name"]',
        '//*[contains(@resource-id, "full_name")]'
    ])
    
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
    
    # === About this account (accessible via username click in action bar) ===
    about_account_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_username_container"]',
    ])
    
    about_account_page_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_title" and @text="About this account"]',
        '//*[@resource-id="com.instagram.android:id/action_bar_title" and @text="À propos de ce compte"]',
    ])
    
    about_account_date_joined_value: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Date joined")]/android.view.View[2]',
        '//*[contains(@content-desc, "Date d\'inscription")]/android.view.View[2]',
    ])
    
    about_account_based_in_value: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Account based in")]/android.view.View[2]',
        '//*[contains(@content-desc, "Compte basé")]/android.view.View[2]',
    ])
    
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
    
    # === Navigation vers DM ===
    # Bouton DM dans la tab bar (depuis le profil ou le feed)
    direct_tab: str = '//*[@resource-id="com.instagram.android:id/direct_tab"]'
    direct_tab_content_desc: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Message"]',
        '//*[@content-desc="Envoyer un message"]',
        '//*[@content-desc="Direct"]',
        '//*[@content-desc="Messages"]',
        '//*[@content-desc="Messenger"]'
    ])
    
    # Badge de notification sur l'onglet DM
    dm_notification_badge: str = '//*[@resource-id="com.instagram.android:id/direct_tab"]//*[@resource-id="com.instagram.android:id/notification"]'
    
    # === Inbox (Liste des conversations) ===
    inbox_thread_list: str = '//*[@resource-id="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview"]'
    
    # Conteneur d'une conversation dans la liste
    thread_container: str = '//*[@resource-id="com.instagram.android:id/row_inbox_container"]'
    
    # Éléments d'une conversation
    thread_username_resource_id: str = 'com.instagram.android:id/row_inbox_username'
    thread_username: str = '//*[@resource-id="com.instagram.android:id/row_inbox_username"]'
    thread_digest: str = '//*[@resource-id="com.instagram.android:id/row_inbox_digest"]'
    thread_timestamp: str = '//*[@resource-id="com.instagram.android:id/row_inbox_timestamp"]'
    thread_avatar: str = '//*[@resource-id="com.instagram.android:id/avatar_container"]'
    
    # Indicateur de message non lu (point bleu)
    unread_indicator: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "non lu")]',
        '//*[contains(@content-desc, "unread")]'
    ])
    
    # === Barre de recherche DM ===
    search_bar: str = '//*[@resource-id="com.instagram.android:id/search_row"]'
    search_edit_text: str = '//*[@resource-id="com.instagram.android:id/search_edit_text"]'
    search_glyph: str = '//*[@resource-id="com.instagram.android:id/search_bar_glyph"]'
    
    # === Filtres de conversation ===
    filter_principal: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Principal")]',
        '//*[contains(@text, "Primary")]'
    ])
    filter_demandes: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Demandes")]',
        '//*[contains(@text, "Requests")]'
    ])
    filter_general: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Général")]',
        '//*[contains(@text, "General")]'
    ])
    
    # === Actions dans l'inbox ===
    new_message_button: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Créer une publicité Envoyer un message"]',
        '//*[contains(@content-desc, "Nouveau message")]',
        '//*[contains(@content-desc, "New message")]',
        '//*[contains(@content-desc, "New Message")]',
        '//*[contains(@content-desc, "Compose")]'
    ])
    
    select_multiple_button: str = '//*[@content-desc="Sélectionner plusieurs messages"]'
    
    # === Navigation dans une conversation ===
    conversation_back_button_resource_id: str = 'com.instagram.android:id/header_left_button'
    
    # === Dans une conversation ===
    message_input: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_thread_composer_edittext"]',
        '//android.widget.EditText[contains(@hint, "Message")]',
        '//android.widget.EditText[contains(@text, "Message")]',
        '//android.widget.EditText[@clickable="true"]'
    ])
    
    send_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_thread_composer_button_send"]',
        '//*[contains(@content-desc, "Envoyer")]',
        '//*[contains(@content-desc, "Send")]',
        '//android.widget.ImageButton[contains(@content-desc, "Envoyer")]',
        '//android.widget.ImageButton[contains(@content-desc, "Send")]'
    ])
    
    # Liste des messages dans une conversation
    message_list: str = '//*[@resource-id="com.instagram.android:id/message_list"]'
    message_item: str = '//*[@resource-id="com.instagram.android:id/direct_text_message_text_view"]'
    message_item_resource_id: str = 'com.instagram.android:id/direct_text_message_text_view'
    
    # === Notes (Stories circulaires en haut des DM) ===
    notes_recycler: str = '//*[@resource-id="com.instagram.android:id/cf_hub_recycler_view"]'
    note_root: str = '//*[@resource-id="com.instagram.android:id/pog_root_view"]'
    note_bubble_text: str = '//*[@resource-id="com.instagram.android:id/pog_bubble_text"]'
    note_name: str = '//*[@resource-id="com.instagram.android:id/pog_name"]'
    add_note_button: str = '//*[@content-desc="Ajouter une note"]'
    
    # === Action bar dans l'inbox ===
    inbox_action_bar: str = '//*[@resource-id="com.instagram.android:id/action_bar_container"]'
    inbox_title: str = '//*[@resource-id="com.instagram.android:id/igds_action_bar_title"]'
    
    # === Legacy selectors (compatibilité) ===
    search_recipient: str = '//android.widget.EditText[contains(@text, "Rechercher") or contains(@text, "Search")]'
    thread_list: str = '//*[@resource-id="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview"]'
    thread_item: str = '//*[@resource-id="com.instagram.android:id/row_inbox_container"]'

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
    
    # Indicateurs de la vue des commentaires (pour éviter confusion avec likers popup)
    comments_view_indicators: List[str] = field(default_factory=lambda: [
        '//*[@text="Comments"]',
        '//*[@text="Commentaires"]',
        '//*[contains(@text, "What do you think")]',
        '//*[contains(@text, "Add a comment")]',
        '//*[contains(@text, "Ajouter un commentaire")]',
        '//*[contains(@hint, "Add a comment")]',
        '//*[contains(@hint, "What do you think")]',
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_edittext"]',
        '//*[@resource-id="com.instagram.android:id/row_comment_textview_comment"]'
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
    
    # === Popup "Review this account before following" ===
    review_account_popup_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Review this account")]',
        '//android.widget.TextView[contains(@text, "before following")]',
        '//android.widget.TextView[contains(@text, "Date joined")]',
        '//android.widget.TextView[contains(@text, "Account based in")]'
    ])
    
    review_account_follow_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Follow"]',
        '//android.widget.Button[@text="Suivre"]',
        '//android.widget.Button[contains(@text, "Follow") and not(contains(@text, "Following"))]'
    ])
    
    review_account_cancel_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Cancel"]',
        '//android.widget.Button[@text="Annuler"]',
        '//android.widget.TextView[@text="Cancel"]',
        '//android.widget.TextView[@text="Annuler"]'
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
    
    # === Comment popup close ===
    comment_popup_drag_handle: str = '//*[@resource-id="com.instagram.android:id/bottom_sheet_drag_handle_prism"]'
    
    # === Unfollow confirmation selectors ===
    unfollow_confirmation_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Ne plus suivre")]',
        '//*[contains(@text, "Unfollow")]',
        '//*[contains(@text, "Confirmer")]',
        '//*[contains(@text, "Confirm")]'
    ])

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
        # Tab selected indicators
        '//*[contains(@content-desc, "Rechercher") and @selected="true"]',
        '//*[contains(@content-desc, "Search") and @selected="true"]',
        # Search bar (when active)
        '//*[contains(@resource-id, "search_edit_text")]',
        # Explore page specific indicators
        '//*[contains(@resource-id, "com.instagram.android:id/clips_tab")]',
        '//*[contains(@resource-id, "com.instagram.android:id/search_tab")]',
        # Search bar on Explore page (clickable text "Search" or "Rechercher")
        '//android.widget.TextView[@package="com.instagram.android" and (contains(@text, "Search") or contains(@text, "Rechercher"))]'
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
    
    reel_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Reel de")]',
        '//*[contains(@content-desc, "Reel by")]',
        '//*[@resource-id="com.instagram.android:id/clips_single_media_component"]',
        '//*[@resource-id="com.instagram.android:id/clips_viewer_video_layout"]',
        '//*[@resource-id="com.instagram.android:id/clips_video_container"]',
        '//*[@resource-id="com.instagram.android:id/clips_video_player"]'
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
    # Quand un post est déjà liké, plusieurs indicateurs possibles selon version/langue:
    # - FR: content-desc = "J'aime déjà" ou "Ne plus aimer"
    # - EN: content-desc = "Unlike" ou "Liked"
    # - Universel: selected = "true" sur le bouton like
    liked_button_indicators: List[str] = field(default_factory=lambda: [
        # === MÉTHODE 1: Attribut selected (le plus fiable, indépendant de la langue) ===
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and @selected="true"]',
        
        # === MÉTHODE 2: Français (FR) ===
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "déjà")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Ne plus aimer")]',
        '//*[contains(@content-desc, "J\'aime déjà")]',
        '//*[contains(@content-desc, "Ne plus aimer")]',
        
        # === MÉTHODE 3: Anglais (EN) ===
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Unlike")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like" and contains(@content-desc, "Liked")]',
        '//*[contains(@content-desc, "Unlike")]',
        
        # === MÉTHODE 4: Fallback générique (anciennes versions) ===
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"][@selected="true"]'
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
    # Sélecteurs SPÉCIFIQUES à la liste des followers/following
    # IMPORTANT: Les éléments comme follow_list_container existent AUSSI sur les profils privés
    # avec des suggestions. On doit utiliser des éléments VRAIMENT uniques.
    followers_list_indicators: List[str] = field(default_factory=lambda: [
        # PRIORITÉ 1: Tab layout avec onglets - N'EXISTE QUE sur la liste des followers
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]',
        # PRIORITÉ 2: View pager de la liste - N'EXISTE QUE sur la liste des followers
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_view_pager"]',
        # PRIORITÉ 3: Onglet "mutual" - N'EXISTE QUE sur la liste des followers
        '//android.widget.Button[contains(@text, "mutual")]',
        # PRIORITÉ 4: Onglet avec nombre + "followers" (ex: "52.5K followers")
        '//android.widget.Button[contains(@text, "followers")]',
    ])
    
    follow_list_username_selectors: List[str] = field(default_factory=lambda: [
        # UNIQUEMENT les vrais followers, PAS les suggestions (row_recommended_user_username)
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        # Pour la popup des likers (bottom sheet)
        '//*[@resource-id="com.instagram.android:id/row_user_primary_name"]'
    ])
    
    # Sélecteurs pour détecter la section suggestions (à éviter)
    suggestions_section_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_recommended_user_username"]',
        '//*[contains(@text, "Voir toutes les suggestions")]',
        '//*[contains(@text, "See all suggestions")]',
        '//*[contains(@text, "Suggestions pour vous")]',
        '//*[contains(@text, "Suggestions for you")]',
        '//*[@resource-id="com.instagram.android:id/row_recommended_user_follow_button"]',
        # "Suggested for you" header in followers list (indicates end of real followers)
        '//*[@resource-id="com.instagram.android:id/row_header_textview" and contains(@text, "Suggested for you")]',
        '//*[@resource-id="com.instagram.android:id/row_header_textview" and contains(@text, "Suggestions pour vous")]'
    ])
    
    # === Limited followers list detection (Meta Verified / Business accounts) ===
    # Instagram limits the number of followers shown for certain accounts
    limited_followers_indicators: List[str] = field(default_factory=lambda: [
        # English message
        '//*[@resource-id="com.instagram.android:id/row_text_textview" and contains(@text, "We limit the number of followers")]',
        '//*[contains(@text, "We limit the number of followers shown")]',
        # French message
        '//*[contains(@text, "Nous limitons le nombre")]',
        '//*[contains(@text, "nombre de followers affiché")]'
    ])
    
    # === End of followers list indicators ===
    # "And X others" message indicates there are more followers but they're hidden
    followers_list_end_indicators: List[str] = field(default_factory=lambda: [
        # "And 12.1K others" pattern (English)
        '//*[@resource-id="com.instagram.android:id/row_text_textview" and contains(@text, "And ") and contains(@text, " others")]',
        # "Et X autres" pattern (French)
        '//*[@resource-id="com.instagram.android:id/row_text_textview" and contains(@text, "Et ") and contains(@text, " autres")]',
        # Generic pattern
        '//*[contains(@text, " others") and @resource-id="com.instagram.android:id/row_text_textview"]'
    ])
    
    # Sélecteurs pour détecter le spinner de chargement Instagram
    loading_spinner_indicators: List[str] = field(default_factory=lambda: [
        # Instagram's "Load more" button with loading animation
        '//*[@resource-id="com.instagram.android:id/row_load_more_button"]',
        # Loading indicator with content-desc
        '//*[contains(@content-desc, "Loading")]',
        '//*[contains(@content-desc, "Chargement")]',
        # Generic progress indicators
        '//android.widget.ProgressBar',
        '//*[@class="android.widget.ProgressBar"]',
        '//*[contains(@resource-id, "progress")]'
    ])
    
    # === Post grid visibility ===
    post_grid_visibility_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_tab_layout"]',
        '//*[contains(@resource-id, "recycler_view")]'
    ])
    
    post_thumbnail_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/image_button"]',
        '//android.widget.ImageView[contains(@resource-id, "image")]'
    ])
    
    # === Private account detection ===
    private_account_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_profile_header_empty_profile_notice_title" and @text="This account is private"]',
        '//*[@resource-id="com.instagram.android:id/row_profile_header_empty_profile_notice_title" and @text="Ce compte est privé"]',
        '//*[contains(@text, "This account is private")]',
        '//*[contains(@text, "Ce compte est privé")]',
        '//*[contains(@content-desc, "This account is private")]',
        '//*[contains(@content-desc, "Ce compte est privé")]'
    ])
    
    # === Verified account detection (Meta Verified / Blue badge) ===
    verified_account_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Verified")]',
        '//*[contains(@content-desc, "Vérifié")]',
        '//*[@resource-id="com.instagram.android:id/verified_badge"]',
        '//*[@resource-id="com.instagram.android:id/action_bar_title_verified_badge"]'
    ])
    
    # === Business account detection ===
    business_account_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "profile_header_business_category")]',
        '//*[contains(@text, "Professional")]',
        '//*[contains(@text, "Professionnel")]'
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
    
    # === Carousel selectors (for atomic extraction) ===
    carousel_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "carousel_video_media_group")]',
        '//*[contains(@resource-id, "carousel_media_group")]',
        '//*[contains(@content-desc, "likes") and contains(@content-desc, "comment")]'
    ])
    
    # === Reel like/comment count selectors ===
    reel_like_count_selector: str = '//*[@resource-id="com.instagram.android:id/like_count"]'
    reel_comment_count_selector: str = '//*[@resource-id="com.instagram.android:id/comment_count"]'
    
    # === Likers list username selectors ===
    likers_list_username_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        '//*[@resource-id="com.instagram.android:id/row_user_username"]',
        '//android.widget.TextView[contains(@text, "@")]'
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
# 🚨 PAGES PROBLÉMATIQUES
# =============================================================================

@dataclass
class ProblematicPageSelectors:
    """Sélecteurs pour la détection et fermeture des pages problématiques."""
    
    # === Boutons de fermeture X/Close ===
    close_button_selectors: List[Dict[str, str]] = field(default_factory=lambda: [
        {'resourceId': 'com.instagram.android:id/action_bar_button_back'},
        {'description': 'Close'},
        {'description': 'Dismiss'},
        {'description': 'Cancel'},
        {'description': 'Fermer'},
        {'description': 'Annuler'},
        {'text': '×'},
        {'text': '✕'},
        {'className': 'android.widget.ImageView', 'description': 'Back'}
    ])
    
    # === Boutons Terminé/Done ===
    terminate_button_selectors: List[Dict[str, str]] = field(default_factory=lambda: [
        {'text': 'Terminé'},
        {'text': 'Done'},
        {'text': 'Fermer'},
        {'text': 'Close'},
        {'description': 'Terminé'},
        {'description': 'Done'}
    ])
    
    # === Boutons OK ===
    ok_button_selectors: List[Dict[str, str]] = field(default_factory=lambda: [
        {'resourceId': 'com.instagram.android:id/igds_alert_dialog_primary_button'},
        {'text': 'OK'},
        {'text': 'Ok'},
        {'textContains': 'OK'},
        {'description': 'OK'},
        {'description': 'Ok'}
    ])
    
    # === Background dimmer (pour fermer les bottom sheets) ===
    background_dimmer_selectors: List[Dict[str, str]] = field(default_factory=lambda: [
        {'resourceId': 'com.instagram.android:id/background_dimmer'},
        {'description': '@2131954182'}
    ])
    
    # === Drag handle (trait gris des bottom sheets) ===
    drag_handle_selectors: List[Dict[str, str]] = field(default_factory=lambda: [
        {'resourceId': 'com.instagram.android:id/bottom_sheet_drag_handle_prism'},
        {'resourceId': 'com.instagram.android:id/bottom_sheet_drag_handle_frame'}
    ])
    
    # === Patterns de détection des pages problématiques ===
    # Chaque pattern contient: indicators (textes à chercher), close_methods, et flags optionnels
    detection_patterns: Dict[str, Dict] = field(default_factory=lambda: {
        'qr_code_page': {
            'indicators': ['Partager le profil', 'QR code', 'Copier le lien'],
            'close_methods': ['back_button', 'x_button', 'tap_outside']
        },
        'story_qr_code_page': {
            'indicators': ['Enregistrer le code QR', 'Terminé', 'Tout le monde peut scanner ce code QR', 'smartphone pour voir ce contenu'],
            'close_methods': ['terminate_button', 'back_button', 'tap_outside']
        },
        'message_contacts_page': {
            'indicators': ['Write a message...', 'Écrivez un message…', 'Send separately', 'Envoyer', 'Search', 'Rechercher', 
                          'Discussion non sélectionnée', 'New group', 'Nouveau groupe', 
                          'direct_private_share_container_view', 'direct_share_sheet_grid_view_pog'],
            'close_methods': ['swipe_down_handle', 'tap_outside', 'back_button']
        },
        'profile_share_page': {
            'indicators': ['WhatsApp', 'Ajouter à la story', 'Partager', 'Texto', 'Threads'],
            'close_methods': ['swipe_down_handle', 'swipe_down', 'tap_outside', 'back_button']
        },
        'try_again_later_page': {
            'indicators': ['Réessayer plus tard', 'Try Again Later', 'Nous limitons la fréquence', 'We limit how often',
                          'certaines actions que vous pouvez effectuer', 'certain things on Instagram',
                          'protéger notre communauté', 'protect our community',
                          'igds_alert_dialog_headline', 'igds_alert_dialog_subtext', 'igds_alert_dialog_primary_button',
                          'Contactez-nous', 'Tell us'],
            'close_methods': ['ok_button', 'back_button'],
            'is_soft_ban': True,
            'track_stats': True
        },
        'notifications_popup': {
            'indicators': ['Notifications', 'Get notifications when', 'shares photos, videos or channels', 
                          'Goes live', 'Some', 'Stories', 'Reels'],
            'close_methods': ['back_button', 'tap_outside', 'swipe_down']
        },
        'follow_notification_popup': {
            'indicators': ['Turn on notifications?', 'Get notifications when', 'Turn On', 'Not Now', 'posts a photo or video'],
            'close_methods': ['not_now_button', 'back_button', 'tap_outside']
        },
        'instagram_update_popup': {
            'indicators': ['Update Instagram', 'Get the latest version', 'Update', 'Not Now', 'available on Google Play'],
            'close_methods': ['not_now_button', 'back_button', 'tap_outside']
        },
        'follow_options_bottom_sheet': {
            'indicators': ['Ajouter à la liste Ami(e)s proches', 'Ajouter aux favoris', 'Sourdine', 
                          'Restreindre', 'Ne plus suivre', 'bottom_sheet_container', 'background_dimmer'],
            'close_methods': ['tap_background_dimmer', 'swipe_down_handle', 'back_button']
        },
        'mute_notifications_popup': {
            'indicators': ['Sourdine', 'Publications', 'Stories', "Bulles d'activité sur le contenu", 
                          'Notes', 'Notes sur la carte', 'Mute', 'Posts', 'Activity bubbles about content',
                          'bottom_sheet_start_nav_button_icon'],
            'close_methods': ['swipe_down_handle', 'swipe_down', 'tap_outside']
        },
        'android_permission_dialog': {
            'indicators': ['com.android.packageinstaller', 'permission_allow_button', 'permission_deny_button',
                          'Autoriser', 'AUTORISER', 'Allow', 'ALLOW', 'accéder aux photos',
                          'access to photos', 'contenus multimédias', 'media files'],
            'close_methods': ['allow_permission_button', 'back_button']
        }
    })

# =============================================================================
# 📸 CRÉATION DE CONTENU
# =============================================================================

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
# 📱 FEED (sélecteurs spécifiques au feed principal)
# =============================================================================

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


# =============================================================================
# 🔓 UNFOLLOW (sélecteurs spécifiques au workflow unfollow)
# =============================================================================

@dataclass
class UnfollowSelectors:
    """Sélecteurs pour le workflow d'unfollow."""
    
    # === Bouton Following/Abonné sur un profil ===
    following_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Abonné")]',
        '//*[contains(@text, "Following")]',
        '//*[contains(@text, "Suivi(e)")]',
        '//*[@resource-id="com.instagram.android:id/profile_header_follow_button" and contains(@text, "Abonné")]',
        '//*[@resource-id="com.instagram.android:id/profile_header_follow_button" and contains(@text, "Following")]'
    ])
    
    # === Bouton Following dans la liste following (pour simple unfollow) ===
    following_list_button_resource_id: str = 'com.instagram.android:id/follow_list_row_large_follow_button'
    following_list_username_resource_id: str = 'com.instagram.android:id/follow_list_username'
    following_tab_title_resource_id: str = 'com.instagram.android:id/title'
    unfollow_confirm_resource_id: str = 'com.instagram.android:id/primary_button'
    
    # === Confirmation d'unfollow dans la popup ===
    unfollow_confirm: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Ne plus suivre")]',
        '//*[contains(@text, "Unfollow")]',
        '//android.widget.Button[contains(@text, "Ne plus suivre")]',
        '//android.widget.Button[contains(@text, "Unfollow")]'
    ])
    
    # === Username dans la liste following ===
    following_list_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]'
    ])
    
    # === Onglet following/abonnements ===
    following_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "following")]',
        '//android.widget.Button[contains(@text, "abonnements")]',
        '//*[contains(@content-desc, "following")]',
        '//*[contains(@content-desc, "abonnements")]'
    ])
    
    # === Tri de la liste ===
    sort_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/sorting_entry_row_icon"]',
        '//*[@content-desc="Sort by"]'
    ])
    
    sort_option_default: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_sorting_option"][@text="Default"]'
    ])
    
    sort_option_latest: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_sorting_option"][@text="Date followed: Latest"]'
    ])
    
    sort_option_earliest: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_sorting_option"][@text="Date followed: Earliest"]'
    ])
    
    # === Détection "follows you back" ===
    follows_back_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Follows you")]',
        '//*[contains(@text, "Vous suit")]',
        '//*[contains(@text, "vous suit")]',
        '//*[contains(@content-desc, "Follows you")]',
        '//*[contains(@content-desc, "Vous suit")]'
    ])
    
    # === Détection bouton Follow après unfollow ===
    follow_button_after_unfollow: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Suivre") and not(contains(@text, "Abonné"))]',
        '//*[contains(@text, "Follow") and not(contains(@text, "Following"))]'
    ])


# =============================================================================
# 🔔 NOTIFICATIONS (sélecteurs spécifiques au workflow notifications)
# =============================================================================

@dataclass
class NotificationSelectors:
    """Sélecteurs pour le workflow notifications/activité."""
    
    # === Onglet activité ===
    activity_tab: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Activité")]',
        '//*[contains(@content-desc, "Activity")]',
        '//*[contains(@content-desc, "Notifications")]'
    ])
    
    # === Éléments de notification ===
    notification_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_news_text"]',
        '//*[@resource-id="com.instagram.android:id/row_news_container"]',
        '//android.widget.LinearLayout[contains(@resource-id, "news")]'
    ])
    
    # === Username dans une notification ===
    notification_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_news_text"]//android.widget.TextView[1]',
        '//android.widget.TextView[contains(@text, "@")]'
    ])
    
    # === Texte d'action de notification ===
    notification_action_text: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_news_text"]',
        '//android.widget.TextView[contains(@text, "liked") or contains(@text, "aimé")]',
        '//android.widget.TextView[contains(@text, "started following") or contains(@text, "a commencé")]',
        '//android.widget.TextView[contains(@text, "commented") or contains(@text, "commenté")]'
    ])
    
    # === Section demandes d'abonnement ===
    follow_requests_section: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Follow requests")]',
        '//*[contains(@text, "Demandes d\'abonnement")]'
    ])
    
    # === Détection écran activité ===
    activity_screen_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Activité")]',
        '//*[contains(@text, "Activity")]',
        '//*[contains(@resource-id, "news")]',
        '//*[contains(@resource-id, "activity")]'
    ])


# =============================================================================
# #️⃣ HASHTAG (sélecteurs spécifiques au workflow hashtag)
# =============================================================================

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


# =============================================================================
# 👥 FOLLOWERS LIST (sélecteurs spécifiques à la liste followers/following)
# =============================================================================

@dataclass
class FollowersListSelectors:
    """Sélecteurs pour la détection et navigation dans la liste followers/following."""
    
    # === Détection liste followers (éléments UNIQUES à cette vue) ===
    list_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]',
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_view_pager"]',
        '//android.widget.Button[contains(@text, "mutual")]',
    ])


# =============================================================================
# 🚀 INSTANCES PRÉDÉFINIES
# =============================================================================

# Instances globales pour une utilisation facile dans tous les modules
FEED_SELECTORS = FeedSelectors()
UNFOLLOW_SELECTORS = UnfollowSelectors()
NOTIFICATION_SELECTORS = NotificationSelectors()
HASHTAG_SELECTORS = HashtagSelectors()
FOLLOWERS_LIST_SELECTORS = FollowersListSelectors()
AUTH_SELECTORS = AuthSelectors()
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
PROBLEMATIC_PAGE_SELECTORS = ProblematicPageSelectors()
CONTENT_CREATION_SELECTORS = ContentCreationSelectors()

# =============================================================================
# 📋 RÉSUMÉ DES SÉLECTEURS DISPONIBLES
# =============================================================================

"""
Structure organisée des sélecteurs UI Instagram :

🔐 AUTH_SELECTORS:
   - Champs de login (username, password)
   - Boutons d'action (login, create account, forgot password)
   - Détection de la page de login
   - Messages d'erreur et états
   - 2FA et vérification
   - Popups post-login
   - Détection de connexion réussie

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
