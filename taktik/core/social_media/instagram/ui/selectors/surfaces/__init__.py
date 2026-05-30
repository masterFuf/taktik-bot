"""Instagram surface selectors.

Owns selectors tied to concrete user-facing Instagram surfaces.
"""

from .content_creation import ContentCreationSelectors, CONTENT_CREATION_SELECTORS
from .direct_messages import DirectMessageSelectors, DM_SELECTORS
from .feed import FeedSelectors, FEED_SELECTORS
from .followers_following import FollowersListSelectors, FOLLOWERS_LIST_SELECTORS
from .hashtag import HashtagSelectors, HASHTAG_SELECTORS
from .notifications import NotificationSelectors, NOTIFICATION_SELECTORS
from .post import (
    PostCommentsSelectors,
    POST_COMMENTS_SELECTORS,
    PostDetailSelectors,
    POST_DETAIL_SELECTORS,
    PostGridSelectors,
    POST_GRID_SELECTORS,
    PostLikersSelectors,
    POST_LIKERS_SELECTORS,
    PostReelsSelectors,
    POST_REELS_SELECTORS,
    PostSelectors,
    POST_SELECTORS,
    PostShareSheetSelectors,
    POST_SHARE_SHEET_SELECTORS,
)
from .profile import ProfileSelectors, PROFILE_SELECTORS
from .story_viewer import StorySelectors, STORY_SELECTORS

__all__ = [
    "CONTENT_CREATION_SELECTORS",
    "DM_SELECTORS",
    "FEED_SELECTORS",
    "FOLLOWERS_LIST_SELECTORS",
    "HASHTAG_SELECTORS",
    "NOTIFICATION_SELECTORS",
    "POST_COMMENTS_SELECTORS",
    "POST_DETAIL_SELECTORS",
    "POST_GRID_SELECTORS",
    "POST_LIKERS_SELECTORS",
    "POST_SELECTORS",
    "POST_REELS_SELECTORS",
    "POST_SHARE_SHEET_SELECTORS",
    "PROFILE_SELECTORS",
    "STORY_SELECTORS",
    "ContentCreationSelectors",
    "DirectMessageSelectors",
    "FeedSelectors",
    "FollowersListSelectors",
    "HashtagSelectors",
    "NotificationSelectors",
    "PostCommentsSelectors",
    "PostDetailSelectors",
    "PostGridSelectors",
    "PostLikersSelectors",
    "PostSelectors",
    "PostReelsSelectors",
    "PostShareSheetSelectors",
    "ProfileSelectors",
    "StorySelectors",
]
