"""UI Selectors — organized by domain.

Each file contains selectors for a specific Instagram UI domain.
Import from here for backward compatibility.
"""

from .auth import AuthSelectors, AUTH_SELECTORS
from .content import ContentCreationSelectors, CONTENT_CREATION_SELECTORS
from .debug import DebugSelectors, DEBUG_SELECTORS
from .detection import DetectionSelectors, DETECTION_SELECTORS
from .dm import DirectMessageSelectors, DM_SELECTORS
from .feed import FeedSelectors, FEED_SELECTORS
from .followers_list import FollowersListSelectors, FOLLOWERS_LIST_SELECTORS
from .hashtag import HashtagSelectors, HASHTAG_SELECTORS
from .navigation import NavigationSelectors, ButtonSelectors, NAVIGATION_SELECTORS, BUTTON_SELECTORS
from .notification import NotificationSelectors, NOTIFICATION_SELECTORS
from .popup import PopupSelectors, POPUP_SELECTORS
from .post import PostSelectors, POST_SELECTORS
from .problematic_page import ProblematicPageSelectors, PROBLEMATIC_PAGE_SELECTORS
from .profile import ProfileSelectors, PROFILE_SELECTORS
from .scroll import ScrollSelectors, SCROLL_SELECTORS
from .story import StorySelectors, STORY_SELECTORS
from .text_input import TextInputSelectors, TEXT_INPUT_SELECTORS
from .unfollow import UnfollowSelectors, UNFOLLOW_SELECTORS

__all__ = [
    'AUTH_SELECTORS',
    'NAVIGATION_SELECTORS',
    'BUTTON_SELECTORS',
    'PROFILE_SELECTORS',
    'POST_SELECTORS',
    'STORY_SELECTORS',
    'DM_SELECTORS',
    'POPUP_SELECTORS',
    'SCROLL_SELECTORS',
    'DETECTION_SELECTORS',
    'TEXT_INPUT_SELECTORS',
    'PROBLEMATIC_PAGE_SELECTORS',
    'CONTENT_CREATION_SELECTORS',
    'DEBUG_SELECTORS',
    'FEED_SELECTORS',
    'UNFOLLOW_SELECTORS',
    'NOTIFICATION_SELECTORS',
    'HASHTAG_SELECTORS',
    'FOLLOWERS_LIST_SELECTORS',
    'AuthSelectors',
    'NavigationSelectors',
    'ButtonSelectors',
    'ProfileSelectors',
    'PostSelectors',
    'StorySelectors',
    'DirectMessageSelectors',
    'PopupSelectors',
    'ScrollSelectors',
    'DetectionSelectors',
    'TextInputSelectors',
    'ProblematicPageSelectors',
    'ContentCreationSelectors',
    'DebugSelectors',
    'FeedSelectors',
    'UnfollowSelectors',
    'NotificationSelectors',
    'HashtagSelectors',
    'FollowersListSelectors',
]
