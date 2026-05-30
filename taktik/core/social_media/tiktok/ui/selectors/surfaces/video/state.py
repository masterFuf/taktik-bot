"""Selectors for video page state and detection on TikTok."""

from dataclasses import dataclass, field
from typing import List

from ._shared import resource_id_with_descendant, resource_ids_with


@dataclass
class VideoStateSelectors:
    """Selectors for stateful video-page detection and toggles."""

    video_liked_indicator: List[str] = field(default_factory=lambda: [
        *resource_ids_with("f4u", xpath_filter='[@selected="true"]'),
        *resource_ids_with("f4u", xpath_filter='[@checked="true"]'),
        *resource_ids_with("f57", xpath_filter='[@selected="true"]'),
        *resource_ids_with("f57", xpath_filter='[@checked="true"]'),
        '//android.widget.ImageView[contains(@content-desc, "Unlike")]',
        '//*[contains(@content-desc, "Retirer") and contains(@content-desc, "J\'aime")]',
        '//*[contains(@content-desc, "Supprimer") and contains(@content-desc, "J\'aime")]',
    ])

    unlike_indicator: List[str] = field(default_factory=lambda: [
        *resource_ids_with("f4u", xpath_filter='[@selected="true"]'),
        *resource_ids_with("f4u", xpath_filter='[@checked="true"]'),
        *resource_ids_with("f57", xpath_filter='[@selected="true"]'),
        *resource_ids_with("f57", xpath_filter='[@checked="true"]'),
        '//*[contains(@content-desc, "Unlike")]',
        '//*[contains(@content-desc, "Liked")]',
        *resource_ids_with("f57", xpath_filter='[contains(@content-desc, "Unlike")]'),
        '//*[contains(@content-desc, "Retirer") and contains(@content-desc, "J\'aime")]',
        '//*[contains(@content-desc, "Supprimer") and contains(@content-desc, "J\'aime")]',
    ])

    video_favorited_indicator: List[str] = field(default_factory=lambda: [
        *resource_ids_with("gtn", xpath_filter='[@selected="true"]'),
        '//*[contains(@content-desc, "Remove from Favourites")]',
        '//*[contains(@content-desc, "Retirer des favoris")]',
    ])

    user_followed_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Following"]',
        '//android.widget.Button[contains(@text, "Friends")]',
        '//*[contains(@content-desc, "Unfollow")]',
    ])

    video_page_indicator: List[str] = field(default_factory=lambda: [
        *resource_ids_with("long_press_layout", xpath_filter='[@content-desc="Video"]'),
        *resource_ids_with("long_press_layout", xpath_filter='[@content-desc="Vid\u00e9o"]'),
        *resource_id_with_descendant("f57", "f4u"),
        *resource_id_with_descendant("f57", "t_j"),
        '//*[contains(@content-desc, "Share video")]',
        '//*[contains(@content-desc, "Partager une vid\u00e9o")]',
    ])

    video_already_liked: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Video liked"]',
        *resource_ids_with("f4u", xpath_filter='[@selected="true"]'),
        *resource_ids_with("f4u", xpath_filter='[@checked="true"]'),
        *resource_ids_with("f57", xpath_filter='[@selected="true"]'),
        *resource_ids_with("f57", xpath_filter='[@checked="true"]'),
        '//*[contains(@content-desc, "Retirer") and contains(@content-desc, "J\'aime")]',
        '//*[contains(@content-desc, "Supprimer") and contains(@content-desc, "J\'aime")]',
    ])

    like_button_unliked: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Like video"]',
        *resource_ids_with("f57", xpath_filter='[contains(@content-desc, "Like video")]'),
        *resource_ids_with("f57", xpath_filter='[contains(@content-desc, "Attribuer un")]'),
        '//*[contains(@content-desc, "Attribuer un")]',
        *resource_id_with_descendant("f57", "f4u"),
    ])

    ad_label: List[str] = field(default_factory=lambda: [
        *resource_ids_with("ru3", xpath_filter='[@text="Ad"]'),
        '//android.widget.TextView[@text="Ad"]',
        '//android.widget.TextView[@text="Sponsorise"]',
        '//android.widget.TextView[@text="Publicite"]',
    ])

    subscribe_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Subscribe")]',
        '//android.widget.Button[contains(@text, "Shop now")]',
        '//android.widget.Button[contains(@text, "Learn more")]',
    ])


VIDEO_STATE_SELECTORS = VideoStateSelectors()
