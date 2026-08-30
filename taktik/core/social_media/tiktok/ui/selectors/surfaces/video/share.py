"""The share sheet of a video, and the one entry a collector needs from it.

Measured on 46.6.3 on 2026-08-30. The sheet a video opens offers: Republier, **Copier le lien**,
Facebook, SMS, Instagram Direct, Email, Signaler, Télécharger — and, from a PROFILE, a slightly
different set (copy link, report, mute, block, message, QR).

What the link is good for, and what it is not. It navigates and it shares, which is all a
`post_url` workflow needs. It does NOT identify: copying the same video's link four times in a row
gave four different `vm.tiktok.com` shortcodes, so the stored identity is built separately (see
`database/tiktok_post_identity.py`).

MEASUREMENT LIMIT, stated rather than glossed: only 46.6.3 share sheets were ever captured, and
both in French. The English entries and the 43.1.4 shape are written from the same structure and
are NOT yet confirmed on a screen.
"""

from typing import List
from dataclasses import dataclass, field

from ...locales import L


@dataclass
class VideoShareSelectors:
    """The share sheet raised by a video, and its copy-link entry."""

    # The sheet is open when its title row is up. Kept language-neutral where possible: the row
    # carries a readable id on 46.6.3, and the localized title is the fallback.
    _sheet_indicator_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/tv_title")]/ancestor::*[contains(@resource-id, ":id/fxs")]',
        '//*[contains(@resource-id, ":id/fxs")]',
    ])

    @property
    def sheet_indicator(self) -> List[str]:
        return self._sheet_indicator_base + L("video_share.sheet_indicator")

    #: The tappable node is the one carrying the CONTENT-DESC; the visible label beneath it is a
    #: child TextView and is not clickable. Both are listed, description first, because tapping
    #: the label works by coordinates but only when it is not clipped.
    @property
    def copy_link_button(self) -> List[str]:
        return L("video_share.copy_link_button")

    @property
    def repost_button(self) -> List[str]:
        return L("video_share.repost_button")


VIDEO_SHARE_SELECTORS = VideoShareSelectors()

__all__ = ["VIDEO_SHARE_SELECTORS", "VideoShareSelectors"]
