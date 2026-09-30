"""Compatibility facade for the TikTok video detail surface."""

from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.creator import VIDEO_CREATOR_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.engagement import VIDEO_ENGAGEMENT_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.media import VIDEO_MEDIA_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.state import VIDEO_STATE_SELECTORS


class VideoSelectors:
    """Backward-compatible aggregate over specialized video selector catalogs."""

    _catalogs = (
        VIDEO_CREATOR_SELECTORS,
        VIDEO_ENGAGEMENT_SELECTORS,
        VIDEO_MEDIA_SELECTORS,
        VIDEO_STATE_SELECTORS,
    )

    def __getattr__(self, name: str):
        for catalog in self._catalogs:
            if hasattr(catalog, name):
                return getattr(catalog, name)
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")


VIDEO_SELECTORS = VideoSelectors()
