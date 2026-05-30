"""TikTok video surface selectors."""

from .comments import CommentSelectors, COMMENT_SELECTORS
from .creator import VideoCreatorSelectors, VIDEO_CREATOR_SELECTORS
from .detail import VideoSelectors, VIDEO_SELECTORS
from .engagement import VideoEngagementSelectors, VIDEO_ENGAGEMENT_SELECTORS
from .media import VideoMediaSelectors, VIDEO_MEDIA_SELECTORS
from .state import VideoStateSelectors, VIDEO_STATE_SELECTORS

VideoDetailSelectors = VideoSelectors
VIDEO_DETAIL_SELECTORS = VIDEO_SELECTORS
VideoCommentsSelectors = CommentSelectors
VIDEO_COMMENTS_SELECTORS = COMMENT_SELECTORS

__all__ = [
    "COMMENT_SELECTORS",
    "VIDEO_COMMENTS_SELECTORS",
    "VIDEO_CREATOR_SELECTORS",
    "VIDEO_DETAIL_SELECTORS",
    "VIDEO_ENGAGEMENT_SELECTORS",
    "VIDEO_MEDIA_SELECTORS",
    "VIDEO_SELECTORS",
    "VIDEO_STATE_SELECTORS",
    "CommentSelectors",
    "VideoCommentsSelectors",
    "VideoCreatorSelectors",
    "VideoDetailSelectors",
    "VideoEngagementSelectors",
    "VideoMediaSelectors",
    "VideoSelectors",
    "VideoStateSelectors",
]
