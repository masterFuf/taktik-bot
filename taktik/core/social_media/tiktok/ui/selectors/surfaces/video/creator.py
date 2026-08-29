"""Selectors for creator identity and follow affordances on TikTok video pages."""

from dataclasses import dataclass, field
from typing import List

from ...locales import L
from ._shared import resource_ids


@dataclass
class VideoCreatorSelectors:
    """Selectors tied to the video author surface."""

    # Evaluated against the RAW hierarchy dump (lxml over `<node class="...">`), not through
    # uiautomator2 -- so a class-based step would never match here. Resource-ids only.
    #
    # `yx4` resolves on neither captured feed; 46.6.3 names the creator avatar `user_avatar`, a
    # name a developer wrote. 43.1.4 exposes no avatar node at all in its dump, so nothing is
    # added for it rather than something invented.
    creator_profile_image_resource_id_selectors: List[str] = field(
        default_factory=lambda: [
            *resource_ids("yx4"),
            '//node[contains(@resource-id, ":id/user_avatar")]',
        ]
    )

    _creator_profile_image_base: List[str] = field(default_factory=lambda: [
        *resource_ids("yx4"),
        '//android.widget.ImageView[contains(@content-desc, "profile")]',
        # A2: readable id, measured on a real 46.6.3 feed. Used as the FALLBACK path for the
        # author name, so it only matters when the text node is missing -- but it was dead.
        '//*[contains(@resource-id, ":id/user_avatar")]',
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
