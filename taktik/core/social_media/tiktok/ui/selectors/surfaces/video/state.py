"""Selectors for video page state and detection on TikTok."""

from dataclasses import dataclass, field
from typing import List

from ...locales import L
from ._shared import resource_id_with_descendant, resource_ids_with


@dataclass
class VideoStateSelectors:
    """Selectors for stateful video-page detection and toggles."""

    _video_liked_indicator_base: List[str] = field(default_factory=lambda: [
        *resource_ids_with("f4u", xpath_filter='[@selected="true"]'),
        *resource_ids_with("f4u", xpath_filter='[@checked="true"]'),
        *resource_ids_with("f57", xpath_filter='[@selected="true"]'),
        *resource_ids_with("f57", xpath_filter='[@checked="true"]'),
    ])

    @property
    def video_liked_indicator(self) -> List[str]:
        return self._video_liked_indicator_base + L("video_state.video_liked_indicator")

    _unlike_indicator_base: List[str] = field(default_factory=lambda: [
        *resource_ids_with("f4u", xpath_filter='[@selected="true"]'),
        *resource_ids_with("f4u", xpath_filter='[@checked="true"]'),
        *resource_ids_with("f57", xpath_filter='[@selected="true"]'),
        *resource_ids_with("f57", xpath_filter='[@checked="true"]'),
    ])

    @property
    def unlike_indicator(self) -> List[str]:
        return self._unlike_indicator_base + L("video_state.unlike_indicator")

    _video_favorited_indicator_base: List[str] = field(default_factory=lambda: [
        *resource_ids_with("gtn", xpath_filter='[@selected="true"]'),
    ])

    @property
    def video_favorited_indicator(self) -> List[str]:
        return self._video_favorited_indicator_base + L("video_state.video_favorited_indicator")

    @property
    def user_followed_indicator(self) -> List[str]:
        return L("video_state.user_followed_indicator")

    _video_page_indicator_base: List[str] = field(default_factory=lambda: [
        *resource_ids_with("long_press_layout", xpath_filter='[@content-desc="Video"]'),
        *resource_ids_with("long_press_layout", xpath_filter='[@content-desc="Vidéo"]'),
        *resource_id_with_descendant("f57", "f4u"),
        *resource_id_with_descendant("f57", "t_j"),
        '//*[contains(@content-desc, "Partager une vidéo")]',
    ])

    @property
    def video_page_indicator(self) -> List[str]:
        return self._video_page_indicator_base + L("video_state.video_page_indicator")

    # Fifteen selectors that answered on NONE of 117 captured screens. `@content-desc="Video
    # liked"` is a label TikTok does not use, and the id half named `f4u`/`f57` — the 43.1.4
    # pair — while 46.6.3 renders `g2c`/`g2w`. So `_is_video_already_liked()` always said no.
    #
    # That is not a missed optimisation. On TikTok, tapping like on an already-liked video
    # UNLIKES it: a check stuck on "no" means the bot removes its own likes on any video it
    # meets twice, and reports a like each time it does.
    #
    # Measured on device 2026-08-30, the same video before and after: the invitation button
    # ("Attribuer un « J'aime » à la vidéo. 35,6 K") DISAPPEARS, and the icon beside it becomes
    # `selected="true"`. The first anchor below reads that second fact and needs no id at all,
    # so it survives the next rename: zero hits before the like, exactly one after, and nothing
    # on any of the 117 other captured screens.
    _video_already_liked_base: List[str] = field(default_factory=lambda: [
        '//*[@selected="true"][contains(@content-desc, "aime") or contains(@content-desc, "ike")'
        ' or contains(@content-desc, "Like")]',
        # 46.6.3's own ids, which the list was missing entirely.
        *resource_ids_with("g2c", xpath_filter='[@selected="true"]'),
        *resource_ids_with("g2w", xpath_filter='[@selected="true"]'),
        # 43.1.4's, kept: they were never disproved, only untested — no capture of a liked video
        # existed on that version.
        *resource_ids_with("f4u", xpath_filter='[@selected="true"]'),
        *resource_ids_with("f4u", xpath_filter='[@checked="true"]'),
        *resource_ids_with("f57", xpath_filter='[@selected="true"]'),
        *resource_ids_with("f57", xpath_filter='[@checked="true"]'),
    ])

    @property
    def video_already_liked(self) -> List[str]:
        return self._video_already_liked_base + L("video_state.video_already_liked")

    _like_button_unliked_base: List[str] = field(default_factory=lambda: [
        *resource_id_with_descendant("f57", "f4u"),
    ])

    @property
    def like_button_unliked(self) -> List[str]:
        return self._like_button_unliked_base + L("video_state.like_button_unliked")

    _ad_label_base: List[str] = field(default_factory=lambda: [
        *resource_ids_with("ru3", xpath_filter='[@text="Ad"]'),
        '//android.widget.TextView[@text="Ad"]',
    ])

    @property
    def ad_label(self) -> List[str]:
        return self._ad_label_base + L("video_state.ad_label")

    _subscribe_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Learn more")]',
    ])

    @property
    def subscribe_button(self) -> List[str]:
        return self._subscribe_button_base + L("video_state.subscribe_button")


VIDEO_STATE_SELECTORS = VideoStateSelectors()
