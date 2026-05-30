"""Instagram surface selectors.

Owns selectors tied to concrete user-facing Instagram surfaces.
"""

from .content_creation import ContentCreationSelectors, CONTENT_CREATION_SELECTORS
from .direct_messages import DirectMessageSelectors, DM_SELECTORS
from .feed import FeedSelectors, FEED_SELECTORS
from .followers_following import FollowersListSelectors, FOLLOWERS_LIST_SELECTORS
from .hashtag import HashtagSelectors, HASHTAG_SELECTORS
from .notifications import NotificationSelectors, NOTIFICATION_SELECTORS
from .profile import ProfileSelectors, PROFILE_SELECTORS
from .story_viewer import StorySelectors, STORY_SELECTORS

__all__ = [
    "CONTENT_CREATION_SELECTORS",
    "DM_SELECTORS",
    "FEED_SELECTORS",
    "FOLLOWERS_LIST_SELECTORS",
    "HASHTAG_SELECTORS",
    "NOTIFICATION_SELECTORS",
    "PROFILE_SELECTORS",
    "STORY_SELECTORS",
    "ContentCreationSelectors",
    "DirectMessageSelectors",
    "FeedSelectors",
    "FollowersListSelectors",
    "HashtagSelectors",
    "NotificationSelectors",
    "ProfileSelectors",
    "StorySelectors",
]
