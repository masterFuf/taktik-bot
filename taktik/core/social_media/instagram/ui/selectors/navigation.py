from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

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
    
    # === Search bar on explore page ===
    explore_search_bar: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Rechercher")]',
        '//android.widget.TextView[contains(@text, "Search")]',
        '//*[@resource-id="com.instagram.android:id/action_bar_search_edit_text"]',
        '//android.widget.EditText[contains(@hint, "Rechercher")]',
        '//android.widget.EditText[contains(@hint, "Search")]',
        '//*[contains(@content-desc, "Rechercher")]',
        '//*[contains(@content-desc, "Search")]',
    ])
    
    # === Search result selectors (use .format(username=...) for dynamic parts) ===
    search_result_container_resource_id: str = 'com.instagram.android:id/row_search_user_container'
    search_result_username_resource_id: str = 'com.instagram.android:id/row_search_user_username'

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

NAVIGATION_SELECTORS = NavigationSelectors()
BUTTON_SELECTORS = ButtonSelectors()
