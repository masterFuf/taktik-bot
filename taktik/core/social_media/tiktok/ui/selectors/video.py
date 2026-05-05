"""Selecteurs UI pour les videos et interactions TikTok."""

from typing import List
from dataclasses import dataclass, field


@dataclass
class VideoSelectors:
    """Selecteurs pour les videos et interactions TikTok.
    
    Compatible v35 (IDs: f57, hi1, f4z text nodes) et v40+ (IDs: fia, i0z, counts in content-desc).
    Les selecteurs sont ordonnes: nouvelle version d abord, ancienne en fallback.
    """

    # === Profil createur ===
    creator_profile_image: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/user_avatar"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/yx4"]',
        '//android.widget.ImageView[contains(@content-desc, "profile")]',
    ])

    # === Bouton Follow ===
    follow_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/i0z"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/hi1"]',
        '//android.widget.Button[contains(@content-desc, "Follow")]',
        '//*[contains(@content-desc, "Follow") and not(contains(@content-desc, "Following")) and not(contains(@content-desc, "Unfollow"))]',
    ])

    # === Bouton Like ===
    like_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/fia"][contains(@content-desc, "Like video")]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Like video")]',
        '//android.widget.Button[contains(@content-desc, "Like video")]',
        '//*[contains(@content-desc, "Like video")]',
    ])

    like_button_for_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/fia"][contains(@content-desc, "Like video")]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Like video")]',
        '//*[contains(@content-desc, "Like video")]',
    ])

    like_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/f4z"]',
    ])

    # === Bouton Comment ===
    comment_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/e4q"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/dtv"]',
        '//android.widget.Button[contains(@content-desc, "comments")]',
        '//*[contains(@content-desc, "Read or add comments")]',
    ])

    comment_button_for_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/e4q"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/dtv"]',
        '//*[contains(@content-desc, "comments")]',
    ])

    comment_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/dp9"]',
    ])

    # === Bouton Favorite ===
    favorite_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/hba"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/guh"]',
        '//android.widget.Button[contains(@content-desc, "Favourites")]',
        '//android.widget.Button[contains(@content-desc, "Favorites")]',
        '//*[contains(@content-desc, "Add or remove this video from Favour")]',
    ])

    favorite_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/gtv"]',
    ])

    # === Bouton Share ===
    share_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/fia"][contains(@content-desc, "Share video")]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Share video")]',
        '//android.widget.Button[contains(@content-desc, "Share video")]',
        '//*[contains(@content-desc, "Share video")]',
    ])

    share_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/t_2"]',
    ])

    # === Bouton Sound ===
    sound_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/oby"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/nhe"]',
        '//android.widget.Button[contains(@content-desc, "Sound:")]',
    ])

    # === Informations video ===
    author_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/user_avatar"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/i0z"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/title"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/ej6"]',
    ])

    video_description: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/desc"]',
    ])

    # === Conteneur video ===
    video_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/long_press_layout"][@content-desc="Video"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/gy_"]',
        '//android.view.View[@content-desc="Video"]',
    ])

    player_view: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/player_view"]',
    ])

    # === Detection etat video ===
    video_liked_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/f4u"][@selected="true"]',
        '//android.widget.ImageView[contains(@content-desc, "Unlike")]',
    ])

    unlike_indicator: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Unlike")]',
        '//*[contains(@content-desc, "Liked")]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/fia"][contains(@content-desc, "Unlike")]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Unlike")]',
    ])

    video_favorited_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/gtn"][@selected="true"]',
        '//*[contains(@content-desc, "Remove from Favour")]',
        '//*[contains(@content-desc, "Retirer des favoris")]',
    ])

    user_followed_indicator: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Unfollow")]',
        '//android.widget.Button[@text="Following"]',
        '//android.widget.Button[@text="Abonne"]',
        '//android.widget.Button[contains(@text, "Friends")]',
    ])

    # === Page detection ===
    video_page_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/long_press_layout"][@content-desc="Video"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/fia"][contains(@content-desc, "Like video")]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Like")]',
        '//*[contains(@content-desc, "Share video")]',
    ])

    video_already_liked: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/fia"][contains(@content-desc, "Unlike")]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Unlike")]',
        '//*[@content-desc="Video liked"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f4u"][@selected="true"]',
    ])

    like_button_unliked: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/fia"][contains(@content-desc, "Like video")]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Like video")]',
        '//*[@content-desc="Like video"]',
    ])

    # === Detection de publicite ===
    ad_label: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ru3"][@text="Ad"]',
        '//android.widget.TextView[@text="Ad"]',
        '//android.widget.TextView[@text="Sponsorise"]',
        '//android.widget.TextView[@text="Publicite"]',
    ])

    # === Bouton Subscribe (publicite) ===
    subscribe_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Subscribe")]',
        '//android.widget.Button[contains(@text, "Shop now")]',
        '//android.widget.Button[contains(@text, "Learn more")]',
    ])


VIDEO_SELECTORS = VideoSelectors()
