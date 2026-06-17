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
