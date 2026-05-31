"""Selectors for creator identity and follow affordances on TikTok video pages."""

from dataclasses import dataclass, field
from typing import List

from ._shared import resource_ids


@dataclass
class VideoCreatorSelectors:
    """Selectors tied to the video author surface."""

    creator_profile_image_resource_id_selectors: List[str] = field(
        default_factory=lambda: [*resource_ids("yx4")]
    )

    creator_profile_image: List[str] = field(default_factory=lambda: [
        *resource_ids("yx4"),
        '//android.widget.ImageView[contains(@content-desc, "profile")]',
        '//android.widget.ImageView[contains(@content-desc, "Profil")]',
    ])

    follow_button: List[str] = field(default_factory=lambda: [
        *resource_ids("hi1"),
        '//android.widget.Button[contains(@content-desc, "Follow")]',
        '//android.widget.Button[contains(@content-desc, "Suivre")]',
        '//*[contains(@content-desc, "Follow") and not(contains(@content-desc, "Following"))]',
    ])

    author_username: List[str] = field(default_factory=lambda: [
        *resource_ids("yx4"),
        *resource_ids("title"),
        *resource_ids("ej6"),
    ])


VIDEO_CREATOR_SELECTORS = VideoCreatorSelectors()
