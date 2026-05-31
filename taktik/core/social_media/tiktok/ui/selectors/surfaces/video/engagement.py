"""Selectors for engagement controls on TikTok video pages."""

from dataclasses import dataclass, field
from typing import List

from ._shared import resource_id_with_descendant, resource_ids, resource_ids_with


@dataclass
class VideoEngagementSelectors:
    """Selectors for like, comment, favorite, and share controls."""

    like_button: List[str] = field(default_factory=lambda: [
        *resource_id_with_descendant("f57", "f4u"),
        *resource_ids_with("f57", xpath_filter='[contains(@content-desc, "Like video")]'),
        *resource_ids_with("f57", xpath_filter='[contains(@content-desc, "Attribuer un")]'),
        '//android.widget.Button[contains(@content-desc, "Like video")]',
        '//android.widget.Button[contains(@content-desc, "Attribuer un")]',
        '//*[contains(@content-desc, "Like video")]',
        '//*[contains(@content-desc, "Attribuer un")]',
    ])

    like_button_content_desc_fallbacks: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Like video")]',
        '//*[contains(@content-desc, "Attribuer un")]',
    ])

    like_button_for_count: List[str] = field(default_factory=lambda: [
        *resource_id_with_descendant("f57", "f4u"),
        *resource_ids_with("f57", xpath_filter='[contains(@content-desc, "Like video")]'),
        *resource_ids_with("f57", xpath_filter='[contains(@content-desc, "Attribuer un")]'),
        '//*[contains(@content-desc, "Like video")]',
        '//*[contains(@content-desc, "Attribuer un")]',
    ])

    like_count: List[str] = field(default_factory=lambda: [*resource_ids("f4z")])

    comment_button: List[str] = field(default_factory=lambda: [
        *resource_ids("dtv"),
        '//android.widget.Button[contains(@content-desc, "comments")]',
        '//*[contains(@content-desc, "Read or add comments")]',
        '//*[contains(@content-desc, "Lire ou ajouter des commentaires")]',
    ])

    comment_button_for_count: List[str] = field(default_factory=lambda: [
        *resource_ids("dtv"),
        '//*[contains(@content-desc, "comments")]',
        '//*[contains(@content-desc, "commentaires")]',
    ])

    comment_count: List[str] = field(default_factory=lambda: [*resource_ids("dp6", "dp9")])

    favorite_button: List[str] = field(default_factory=lambda: [
        *resource_ids("guh"),
        '//android.widget.Button[contains(@content-desc, "Favourites")]',
        '//android.widget.Button[contains(@content-desc, "Favorites")]',
        '//*[contains(@content-desc, "Add or remove this video from Favour")]',
        '//*[contains(@content-desc, "Ajoute ou supprime cette vid\u00e9o de tes Favoris")]',
    ])

    favorite_count: List[str] = field(default_factory=lambda: [*resource_ids("gtv")])

    share_button: List[str] = field(default_factory=lambda: [
        *resource_id_with_descendant("f57", "t_j"),
        *resource_ids_with("f57", xpath_filter='[contains(@content-desc, "Share video")]'),
        *resource_ids_with("f57", xpath_filter='[contains(@content-desc, "Partager une vid\u00e9o")]'),
        '//android.widget.Button[contains(@content-desc, "Share video")]',
        '//android.widget.Button[contains(@content-desc, "Partager une vid\u00e9o")]',
        '//*[contains(@content-desc, "Share video")]',
        '//*[contains(@content-desc, "Partager une vid\u00e9o")]',
    ])

    share_count: List[str] = field(default_factory=lambda: [*resource_ids("t_2")])


VIDEO_ENGAGEMENT_SELECTORS = VideoEngagementSelectors()
