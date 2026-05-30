"""TikTok video surface selectors."""

from .comments import CommentSelectors, COMMENT_SELECTORS
from .detail import VideoSelectors, VIDEO_SELECTORS

VideoDetailSelectors = VideoSelectors
VIDEO_DETAIL_SELECTORS = VIDEO_SELECTORS
VideoCommentsSelectors = CommentSelectors
VIDEO_COMMENTS_SELECTORS = COMMENT_SELECTORS

__all__ = [
    "COMMENT_SELECTORS",
    "VIDEO_COMMENTS_SELECTORS",
    "VIDEO_DETAIL_SELECTORS",
    "VIDEO_SELECTORS",
    "CommentSelectors",
    "VideoCommentsSelectors",
    "VideoDetailSelectors",
    "VideoSelectors",
]
