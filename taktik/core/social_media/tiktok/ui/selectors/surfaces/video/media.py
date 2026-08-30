"""Selectors for media content on TikTok video pages."""

from dataclasses import dataclass, field
from typing import List

from ._shared import resource_ids, resource_ids_with
from ...locales import L


@dataclass
class VideoMediaSelectors:
    """Selectors for playable media and descriptive metadata."""

    _sound_button_base: List[str] = field(default_factory=lambda: [
        *resource_ids("nhe"),
    ])

    @property
    def sound_button(self) -> List[str]:
        return self._sound_button_base + L("video_media.sound_button")

    #: The publication date, exactly as the screen writes it: `· 06-12`, `· Il y a 7 h`. A
    #: LABEL, not a date — parsing it into one would invent a precision TikTok does not give.
    #: Measured on four captured video screens, one match each, on a readable id.
    #: It is one third of a post's stable identity (`database/tiktok_post_identity.py`), the
    #: link being useless for that: TikTok mints a new short link on every copy.
    post_time: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/tv_post_time")]',
    ])

    video_description: List[str] = field(default_factory=lambda: [*resource_ids("desc")])

    video_container: List[str] = field(default_factory=lambda: [
        *resource_ids_with("long_press_layout", xpath_filter='[@content-desc="Video"]'),
        *resource_ids_with("long_press_layout", xpath_filter='[@content-desc="Vid\u00e9o"]'),
        *resource_ids("gy_"),
        '//android.view.View[@content-desc="Video"]',
        '//android.view.View[@content-desc="Vid\u00e9o"]',
    ])

    player_view: List[str] = field(default_factory=lambda: [*resource_ids("player_view")])


VIDEO_MEDIA_SELECTORS = VideoMediaSelectors()
