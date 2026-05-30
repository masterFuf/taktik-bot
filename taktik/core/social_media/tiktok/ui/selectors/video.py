"""Compatibility shim for TikTok video surface selectors."""

from .surfaces.video import VideoSelectors, VIDEO_SELECTORS, VideoDetailSelectors, VIDEO_DETAIL_SELECTORS

__all__ = [
    "VIDEO_DETAIL_SELECTORS",
    "VIDEO_SELECTORS",
    "VideoDetailSelectors",
    "VideoSelectors",
]
