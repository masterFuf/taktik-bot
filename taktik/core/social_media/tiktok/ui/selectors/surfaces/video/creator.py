"""Selectors for creator identity and follow affordances on TikTok video pages."""

from dataclasses import dataclass, field
from typing import List

from ...locales import L
from ._shared import resource_ids


@dataclass
class VideoCreatorSelectors:
    """Selectors tied to the video author surface."""

    creator_profile_image_resource_id_selectors: List[str] = field(
        default_factory=lambda: [*resource_ids("yx4")]
    )

    _creator_profile_image_base: List[str] = field(default_factory=lambda: [
        *resource_ids("yx4"),
        '//android.widget.ImageView[contains(@content-desc, "profile")]',
    ])

    @property
    def creator_profile_image(self) -> List[str]:
        return self._creator_profile_image_base + L("video_creator.creator_profile_image")

    _follow_button_base: List[str] = field(default_factory=lambda: [
        *resource_ids("hi1"),
    ])

    @property
    def follow_button(self) -> List[str]:
        return self._follow_button_base + L("video_creator.follow_button")

    author_username: List[str] = field(default_factory=lambda: [
        *resource_ids("yx4"),
        *resource_ids("title"),
        *resource_ids("ej6"),
    ])


VIDEO_CREATOR_SELECTORS = VideoCreatorSelectors()
