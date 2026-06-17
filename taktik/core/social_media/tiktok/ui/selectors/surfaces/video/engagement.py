"""Selectors for engagement controls on TikTok video pages."""

from dataclasses import dataclass, field
from typing import List

from ._shared import resource_id_with_descendant, resource_ids, resource_ids_with
from ...locales import L


@dataclass
class VideoEngagementSelectors:
    """Selectors for like, comment, favorite, and share controls."""

    _like_button_base: List[str] = field(default_factory=lambda: [
        *resource_id_with_descendant("f57", "f4u"),
    ])

    @property
    def like_button(self) -> List[str]:
        return self._like_button_base + L("video_engagement.like_button")

    @property
    def like_button_content_desc_fallbacks(self) -> List[str]:
        return L("video_engagement.like_button_content_desc_fallbacks")

    _like_button_for_count_base: List[str] = field(default_factory=lambda: [
        *resource_id_with_descendant("f57", "f4u"),
    ])

    @property
    def like_button_for_count(self) -> List[str]:
        return self._like_button_for_count_base + L("video_engagement.like_button_for_count")

    like_count: List[str] = field(default_factory=lambda: [*resource_ids("f4z")])

    _comment_button_base: List[str] = field(default_factory=lambda: [
        *resource_ids("dtv"),
        '//android.widget.Button[contains(@content-desc, "comments")]',
    ])

    @property
    def comment_button(self) -> List[str]:
        return self._comment_button_base + L("video_engagement.comment_button")

    _comment_button_for_count_base: List[str] = field(default_factory=lambda: [
        *resource_ids("dtv"),
        '//*[contains(@content-desc, "comments")]',
    ])

    @property
    def comment_button_for_count(self) -> List[str]:
        return self._comment_button_for_count_base + L("video_engagement.comment_button_for_count")

    comment_count: List[str] = field(default_factory=lambda: [*resource_ids("dp6", "dp9")])

    _favorite_button_base: List[str] = field(default_factory=lambda: [
        *resource_ids("guh"),
    ])

    @property
    def favorite_button(self) -> List[str]:
        return self._favorite_button_base + L("video_engagement.favorite_button")

    favorite_count: List[str] = field(default_factory=lambda: [*resource_ids("gtv")])

    _share_button_base: List[str] = field(default_factory=lambda: [
        *resource_id_with_descendant("f57", "t_j"),
        *resource_ids_with("f57", xpath_filter='[contains(@content-desc, "Partager une vidéo")]'),
        '//android.widget.Button[contains(@content-desc, "Partager une vidéo")]',
        '//*[contains(@content-desc, "Partager une vidéo")]',
    ])

    @property
    def share_button(self) -> List[str]:
        return self._share_button_base + L("video_engagement.share_button")

    share_count: List[str] = field(default_factory=lambda: [*resource_ids("t_2")])


VIDEO_ENGAGEMENT_SELECTORS = VideoEngagementSelectors()
