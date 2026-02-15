from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

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
    
    # === Profile picture (for screenshot + crop extraction) ===
    profile_picture_imageview: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_profile_header_imageview"]',
        '//*[@resource-id="com.instagram.android:id/profile_header_avatar"]',
        '//*[@resource-id="com.instagram.android:id/profile_header_avatar_image"]',
        '//*[@resource-id="com.instagram.android:id/profile_pic"]',
    ])
    
    # === Enrichment selectors (XML-based profile extraction) ===
    enrichment_username_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_title"]',
        '//*[@resource-id="com.instagram.android:id/action_bar_username_container"]//android.widget.TextView',
    ])
    
    enrichment_full_name_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_header_full_name_above_vanity"]',
        '//*[@resource-id="com.instagram.android:id/profile_header_full_name"]',
    ])
    
    enrichment_category_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_header_business_category"]',
    ])
    
    enrichment_bio_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_user_info_compose_view"]//android.widget.TextView',
        '//*[@resource-id="com.instagram.android:id/profile_user_info_compose_view"]//*[@class="android.widget.TextView"]',
        '//*[@resource-id="com.instagram.android:id/profile_header_bio_text"]',
    ])
    
    enrichment_website_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_links_view"]//*[@resource-id="com.instagram.android:id/text_view"]',
        '//*[@resource-id="com.instagram.android:id/profile_header_website"]',
    ])
    
    enrichment_banner_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/banner_row"]//*[@resource-id="com.instagram.android:id/profile_header_banner_item_layout"]',
    ])
    
    enrichment_banner_title_selector: str = './/*[@resource-id="com.instagram.android:id/profile_header_banner_item_title"]'
    
    enrichment_bio_more_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_user_info_compose_view"]//*[contains(@text, "more")]',
        '//*[contains(@text, "… more")]',
        '//*[contains(@text, "...more")]',
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

PROFILE_SELECTORS = ProfileSelectors()
