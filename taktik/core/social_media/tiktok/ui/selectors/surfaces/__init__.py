"""TikTok surface selectors."""

from .conversation import ConversationSelectors, CONVERSATION_SELECTORS
from .followers import FollowersSelectors, FOLLOWERS_SELECTORS
from .inbox import InboxSelectors, INBOX_SELECTORS
from .profile import ProfileSelectors, PROFILE_SELECTORS
from .search import SearchSelectors, SEARCH_SELECTORS
from .video import (
    CommentSelectors,
    COMMENT_SELECTORS,
    VideoCommentsSelectors,
    VIDEO_COMMENTS_SELECTORS,
    VideoDetailSelectors,
    VIDEO_DETAIL_SELECTORS,
    VideoSelectors,
    VIDEO_SELECTORS,
)

__all__ = [
    "COMMENT_SELECTORS",
    "CONVERSATION_SELECTORS",
    "FOLLOWERS_SELECTORS",
    "INBOX_SELECTORS",
    "PROFILE_SELECTORS",
    "SEARCH_SELECTORS",
    "VIDEO_COMMENTS_SELECTORS",
    "VIDEO_DETAIL_SELECTORS",
    "VIDEO_SELECTORS",
    "CommentSelectors",
    "ConversationSelectors",
    "FollowersSelectors",
    "InboxSelectors",
    "ProfileSelectors",
    "SearchSelectors",
    "VideoCommentsSelectors",
    "VideoDetailSelectors",
    "VideoSelectors",
]
