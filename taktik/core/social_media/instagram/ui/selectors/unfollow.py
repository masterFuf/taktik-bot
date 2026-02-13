from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

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

UNFOLLOW_SELECTORS = UnfollowSelectors()
