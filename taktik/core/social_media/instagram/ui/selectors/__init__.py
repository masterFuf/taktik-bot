"""Instagram UI selectors.

The package is being reorganized by UI scope (`shell`, `surfaces`, `flows`,
`support`) while keeping the historical top-level imports stable.
"""

from .content import ContentCreationSelectors, CONTENT_CREATION_SELECTORS
from .debug import DebugSelectors, DEBUG_SELECTORS
from .dm import DirectMessageSelectors, DM_SELECTORS
from .feed import FeedSelectors, FEED_SELECTORS
from .followers_list import FollowersListSelectors, FOLLOWERS_LIST_SELECTORS
from .hashtag import HashtagSelectors, HASHTAG_SELECTORS
from .navigation import NavigationSelectors, ButtonSelectors, NAVIGATION_SELECTORS, BUTTON_SELECTORS
from .notification import NotificationSelectors, NOTIFICATION_SELECTORS
from .post import PostSelectors, POST_SELECTORS
from .profile import ProfileSelectors, PROFILE_SELECTORS
from .scroll import ScrollSelectors, SCROLL_SELECTORS
from .shell import (
    AuthSelectors,
    AUTH_SELECTORS,
    DetectionSelectors,
    DETECTION_SELECTORS,
    PopupSelectors,
    POPUP_SELECTORS,
    ProblematicPageSelectors,
    PROBLEMATIC_PAGE_SELECTORS,
    TextInputSelectors,
    TEXT_INPUT_SELECTORS,
)
from .story import StorySelectors, STORY_SELECTORS
from .unfollow import UnfollowSelectors, UNFOLLOW_SELECTORS

__all__ = [
    "AUTH_SELECTORS",
    "NAVIGATION_SELECTORS",
    "BUTTON_SELECTORS",
    "PROFILE_SELECTORS",
    "POST_SELECTORS",
    "STORY_SELECTORS",
    "DM_SELECTORS",
    "POPUP_SELECTORS",
    "SCROLL_SELECTORS",
    "DETECTION_SELECTORS",
    "TEXT_INPUT_SELECTORS",
    "PROBLEMATIC_PAGE_SELECTORS",
    "CONTENT_CREATION_SELECTORS",
    "DEBUG_SELECTORS",
    "FEED_SELECTORS",
    "UNFOLLOW_SELECTORS",
    "NOTIFICATION_SELECTORS",
    "HASHTAG_SELECTORS",
    "FOLLOWERS_LIST_SELECTORS",
    "AuthSelectors",
    "NavigationSelectors",
    "ButtonSelectors",
    "ProfileSelectors",
    "PostSelectors",
    "StorySelectors",
    "DirectMessageSelectors",
    "PopupSelectors",
    "ScrollSelectors",
    "DetectionSelectors",
    "TextInputSelectors",
    "ProblematicPageSelectors",
    "ContentCreationSelectors",
    "DebugSelectors",
    "FeedSelectors",
    "UnfollowSelectors",
    "NotificationSelectors",
    "HashtagSelectors",
    "FollowersListSelectors",
]
