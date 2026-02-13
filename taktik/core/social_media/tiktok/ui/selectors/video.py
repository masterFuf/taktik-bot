"""Sélecteurs UI pour les vidéos et interactions TikTok."""

from typing import List
from dataclasses import dataclass, field


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
        '//*[@resource-id="com.zhiliaoapp.musically:id/ej6"]',
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
    
    # Unlike indicators (content-desc changes from "Like" to "Unlike" when liked)
    unlike_indicator: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Unlike")]',
        '//*[contains(@content-desc, "Liked")]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Unlike")]',
    ])
    
    video_favorited_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/gtn"][@selected="true"]',
        '//*[contains(@content-desc, "Remove from Favourites")]',
        '//*[contains(@content-desc, "Retirer des favoris")]',
    ])
    
    # User followed state (button text changes from "Follow" to "Following"/"Friends")
    user_followed_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Following"]',
        '//android.widget.Button[@text="Abonné"]',
        '//android.widget.Button[contains(@text, "Friends")]',
        '//*[contains(@content-desc, "Unfollow")]',
    ])
    
    # === Page detection: video playback ===
    video_page_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/long_press_layout"][@content-desc="Video"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][@content-desc="Video liked"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Like")]',
        '//*[contains(@content-desc, "Share video")]',
    ])
    
    # Already-liked indicator (content-desc = "Video liked")
    video_already_liked: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Video liked"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f4u"][@selected="true"]',
    ])
    
    # Like button (only for unliked videos)
    like_button_unliked: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Like video"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Like video")]',
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


VIDEO_SELECTORS = VideoSelectors()
