"""Selecteurs UI pour les videos et interactions TikTok."""

from typing import List
from dataclasses import dataclass, field

# Known TikTok package names (IDs are identical across variants)
_PKG = [
    "com.zhiliaoapp.musically",
    "com.ss.android.ugc.trill",
    "com.ss.android.ugc.aweme",
]

def _rids(*ids):
    """Generate resource-id selectors for all known TikTok packages."""
    return [f'//*[@resource-id="{pkg}:id/{rid}"]' for rid in ids for pkg in _PKG]

def _rid_with(*ids_and_filter):
    """Like _rids but appends an XPath filter (e.g. '[@text="Ad"]') to each selector."""
    ids, xpath_filter = ids_and_filter[:-1], ids_and_filter[-1]
    return [f'//*[@resource-id="{pkg}:id/{rid}"]{xpath_filter}' for rid in ids for pkg in _PKG]


@dataclass
class VideoSelectors:
    """Selecteurs pour les videos et interactions TikTok.

    Compatible com.zhiliaoapp.musically (international) et com.ss.android.ugc.trill (Trill).
    Les IDs sont identiques entre les deux variants - seul le package prefix differe.
    """

    # === Profil createur ===
    creator_profile_image: List[str] = field(default_factory=lambda: [
        *_rids("yx4"),
        '//android.widget.ImageView[contains(@content-desc, "profile")]',
    ])

    # === Bouton Follow ===
    follow_button: List[str] = field(default_factory=lambda: [
        *_rids("hi1"),
        '//android.widget.Button[contains(@content-desc, "Follow")]',
        '//*[contains(@content-desc, "Follow") and not(contains(@content-desc, "Following"))]',
    ])

    # === Bouton Like ===
    like_button: List[str] = field(default_factory=lambda: [
        *_rid_with("f57", '[contains(@content-desc, "Like video")]'),
        '//android.widget.Button[contains(@content-desc, "Like video")]',
        '//*[contains(@content-desc, "Like video")]',
    ])

    # Selecteur like pour extraire le count depuis content-desc
    like_button_for_count: List[str] = field(default_factory=lambda: [
        *_rid_with("f57", '[contains(@content-desc, "Like video")]'),
    ])

    like_count: List[str] = field(default_factory=lambda: [
        *_rids("f4z"),
    ])

    # === Bouton Comment ===
    comment_button: List[str] = field(default_factory=lambda: [
        *_rids("dtv"),
        '//android.widget.Button[contains(@content-desc, "comments")]',
        '//*[contains(@content-desc, "Read or add comments")]',
    ])

    comment_button_for_count: List[str] = field(default_factory=lambda: [
        *_rids("dtv"),
        '//*[contains(@content-desc, "comments")]',
    ])

    comment_count: List[str] = field(default_factory=lambda: [
        *_rids("dp9"),
    ])

    # === Bouton Favorite ===
    favorite_button: List[str] = field(default_factory=lambda: [
        *_rids("guh"),
        '//android.widget.Button[contains(@content-desc, "Favourites")]',
        '//android.widget.Button[contains(@content-desc, "Favorites")]',
        '//*[contains(@content-desc, "Add or remove this video from Favour")]',
    ])

    favorite_count: List[str] = field(default_factory=lambda: [
        *_rids("gtv"),
    ])

    # === Bouton Share ===
    share_button: List[str] = field(default_factory=lambda: [
        *_rid_with("f57", '[contains(@content-desc, "Share video")]'),
        '//android.widget.Button[contains(@content-desc, "Share video")]',
        '//*[contains(@content-desc, "Share video")]',
    ])

    share_count: List[str] = field(default_factory=lambda: [
        *_rids("t_2"),
    ])

    # === Bouton Sound ===
    sound_button: List[str] = field(default_factory=lambda: [
        *_rids("nhe"),
        '//android.widget.Button[contains(@content-desc, "Sound:")]',
    ])

    # === Informations video ===
    # author_username utilise l avatar (content-desc="username profile") en priorite
    author_username: List[str] = field(default_factory=lambda: [
        *_rids("yx4"),
        *_rids("title"),
        *_rids("ej6"),
    ])

    video_description: List[str] = field(default_factory=lambda: [
        *_rids("desc"),
    ])

    # === Conteneur video ===
    video_container: List[str] = field(default_factory=lambda: [
        *_rid_with("long_press_layout", '[@content-desc="Video"]'),
        *_rids("gy_"),
        '//android.view.View[@content-desc="Video"]',
    ])

    player_view: List[str] = field(default_factory=lambda: [
        *_rids("player_view"),
    ])

    # === Detection etat video ===
    video_liked_indicator: List[str] = field(default_factory=lambda: [
        *_rid_with("f4u", '[@selected="true"]'),
        '//android.widget.ImageView[contains(@content-desc, "Unlike")]',
    ])

    unlike_indicator: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Unlike")]',
        '//*[contains(@content-desc, "Liked")]',
        *_rid_with("f57", '[contains(@content-desc, "Unlike")]'),
    ])

    video_favorited_indicator: List[str] = field(default_factory=lambda: [
        *_rid_with("gtn", '[@selected="true"]'),
        '//*[contains(@content-desc, "Remove from Favourites")]',
        '//*[contains(@content-desc, "Retirer des favoris")]',
    ])

    user_followed_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Following"]',
        '//android.widget.Button[contains(@text, "Friends")]',
        '//*[contains(@content-desc, "Unfollow")]',
    ])

    # === Page detection ===
    video_page_indicator: List[str] = field(default_factory=lambda: [
        *_rid_with("long_press_layout", '[@content-desc="Video"]'),
        *_rid_with("f57", '[contains(@content-desc, "Like")]'),
        '//*[contains(@content-desc, "Share video")]',
    ])

    video_already_liked: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Video liked"]',
        *_rid_with("f4u", '[@selected="true"]'),
    ])

    like_button_unliked: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Like video"]',
        *_rid_with("f57", '[contains(@content-desc, "Like video")]'),
    ])

    # === Detection de publicite ===
    ad_label: List[str] = field(default_factory=lambda: [
        *_rid_with("ru3", '[@text="Ad"]'),
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
