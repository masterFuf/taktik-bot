"""Compatibility shim for TikTok video surface selectors."""

from .surfaces.video import (
    VideoCreatorSelectors,
    VIDEO_CREATOR_SELECTORS,
    VideoDetailSelectors,
    VIDEO_DETAIL_SELECTORS,
    VideoEngagementSelectors,
    VIDEO_ENGAGEMENT_SELECTORS,
    VideoMediaSelectors,
    VIDEO_MEDIA_SELECTORS,
    VideoSelectors,
    VIDEO_SELECTORS,
    VideoStateSelectors,
    VIDEO_STATE_SELECTORS,
)

__all__ = [
    "VIDEO_CREATOR_SELECTORS",
    "VIDEO_DETAIL_SELECTORS",
    "VIDEO_ENGAGEMENT_SELECTORS",
    "VIDEO_MEDIA_SELECTORS",
    "VIDEO_SELECTORS",
    "VIDEO_STATE_SELECTORS",
    "VideoCreatorSelectors",
    "VideoDetailSelectors",
    "VideoEngagementSelectors",
    "VideoMediaSelectors",
    "VideoSelectors",
    "VideoStateSelectors",
]
