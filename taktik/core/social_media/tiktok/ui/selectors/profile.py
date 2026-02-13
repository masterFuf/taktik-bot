"""Sélecteurs UI pour les profils utilisateurs TikTok."""

from typing import List
from dataclasses import dataclass, field


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
        '//*[@resource-id="com.zhiliaoapp.musically:id/eme"][@text="Message"]',
        '//android.widget.TextView[@text="Message"]',
    ])
    
    # === Page detection: profile page ===
    profile_page_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qh5"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/qfv"][@text="Followers"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/qfv"][@text="Following"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/gxd"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/w4m"][@text="No videos yet"]',
    ])
    
    # Bio text (resource-id: qfx)
    bio_text: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qfx"]',
    ])
    
    # Verified badge
    verified_badge: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Verified")]',
    ])
    
    # Private account indicator
    private_indicator: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "private")]',
    ])
    
    # === Story page detection ===
    story_timestamp: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/xyx"]',
    ])
    
    story_close_button: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Close"][@clickable="true"]',
    ])
    
    story_follow_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdo"]',
    ])
    
    story_message_input: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qwz"][@text="Message..."]',
    ])
    
    story_page_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/xyx"]',
        '//*[@content-desc="Close"][@clickable="true"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdo"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/qwz"][@text="Message..."]',
    ])
    
    # Story username (clickable, leads to profile)
    story_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/title"][@clickable="true"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/s28"]//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/title"]',
    ])
    
    # === Privacy blocked conversation indicators ===
    unable_to_send_message: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/w4m"][@text="Unable to send message"]',
        '//*[@text="Unable to send message"]',
        '//*[contains(@text, "Unable to send")]',
    ])
    
    privacy_blocked_message: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/uq5"]',
        '//*[contains(@text, "privacy settings")]',
        '//*[contains(@text, "Cannot send message")]',
    ])


PROFILE_SELECTORS = ProfileSelectors()
