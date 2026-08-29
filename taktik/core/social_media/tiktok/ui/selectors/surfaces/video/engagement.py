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

    _like_count_base: List[str] = field(default_factory=lambda: [*resource_ids("f4z")])

    @property
    def like_count(self) -> List[str]:
        return self._like_count_base + L("video_engagement.like_count_anchors")

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

    _comment_count_base: List[str] = field(default_factory=lambda: [*resource_ids("dp6", "dp9")])

    @property
    def comment_count(self) -> List[str]:
        return self._comment_count_base + L("video_engagement.comment_count_anchors")

    _favorite_button_base: List[str] = field(default_factory=lambda: [
        *resource_ids("guh"),
    ])

    @property
    def favorite_button(self) -> List[str]:
        return self._favorite_button_base + L("video_engagement.favorite_button")

    _favorite_count_base: List[str] = field(default_factory=lambda: [*resource_ids("gtv")])

    @property
    def favorite_count(self) -> List[str]:
        return self._favorite_count_base + L("video_engagement.favorite_count_anchors")

    _share_button_base: List[str] = field(default_factory=lambda: [
        *resource_id_with_descendant("f57", "t_j"),
        *resource_ids_with("f57", xpath_filter='[contains(@content-desc, "Partager une vidéo")]'),
        '//android.widget.Button[contains(@content-desc, "Partager une vidéo")]',
        '//*[contains(@content-desc, "Partager une vidéo")]',
    ])

    @property
    def share_button(self) -> List[str]:
        return self._share_button_base + L("video_engagement.share_button")

    _share_count_base: List[str] = field(default_factory=lambda: [*resource_ids("t_2")])

    @property
    def share_count(self) -> List[str]:
        return self._share_count_base + L("video_engagement.share_count_anchors")


VIDEO_ENGAGEMENT_SELECTORS = VideoEngagementSelectors()
