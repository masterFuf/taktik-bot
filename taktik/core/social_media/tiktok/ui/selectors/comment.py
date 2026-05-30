"""Compatibility shim for TikTok video-comments selectors."""

from .surfaces.video import (
    COMMENT_SELECTORS,
    VIDEO_COMMENTS_SELECTORS,
    CommentSelectors,
    VideoCommentsSelectors,
)

__all__ = [
    "COMMENT_SELECTORS",
    "VIDEO_COMMENTS_SELECTORS",
    "CommentSelectors",
    "VideoCommentsSelectors",
]
