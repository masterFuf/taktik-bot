"""TikTok UI selectors.

The package is being reorganized by UI scope (`shell`, `surfaces`, `flows`,
`support`) while keeping historical top-level imports stable.
"""

from .auth import (
    AuthSelectors,
    AUTH_SELECTORS,
    SignupSelectors,
    SIGNUP_SELECTORS,
    LogoutSelectors,
    LOGOUT_SELECTORS,
    CountryPickerSelectors,
    COUNTRY_PICKER_SELECTORS,
    TIKTOK_PACKAGE,
)
from .comment import CommentSelectors, COMMENT_SELECTORS
from .publish import PublishSelectors, PUBLISH_SELECTORS
from .shell import (
    DetectionSelectors,
    DETECTION_SELECTORS,
    NavigationSelectors,
    NAVIGATION_SELECTORS,
    PopupSelectors,
    POPUP_SELECTORS,
)
from .support import ScrollSelectors, SCROLL_SELECTORS
from .surfaces import (
    ConversationSelectors,
    CONVERSATION_SELECTORS,
    FollowersSelectors,
    FOLLOWERS_SELECTORS,
    InboxSelectors,
    INBOX_SELECTORS,
    ProfileSelectors,
    PROFILE_SELECTORS,
    SearchSelectors,
    SEARCH_SELECTORS,
)
from .video import VideoSelectors, VIDEO_SELECTORS

__all__ = [
    "TIKTOK_PACKAGE",
    "AuthSelectors",
    "SignupSelectors",
    "LogoutSelectors",
    "CountryPickerSelectors",
    "NavigationSelectors",
    "ProfileSelectors",
    "VideoSelectors",
    "InboxSelectors",
    "ConversationSelectors",
    "CommentSelectors",
    "SearchSelectors",
    "PopupSelectors",
    "ScrollSelectors",
    "DetectionSelectors",
    "FollowersSelectors",
    "PublishSelectors",
    "AUTH_SELECTORS",
    "SIGNUP_SELECTORS",
    "LOGOUT_SELECTORS",
    "COUNTRY_PICKER_SELECTORS",
    "NAVIGATION_SELECTORS",
    "PROFILE_SELECTORS",
    "VIDEO_SELECTORS",
    "COMMENT_SELECTORS",
    "SEARCH_SELECTORS",
    "INBOX_SELECTORS",
    "CONVERSATION_SELECTORS",
    "POPUP_SELECTORS",
    "SCROLL_SELECTORS",
    "DETECTION_SELECTORS",
    "FOLLOWERS_SELECTORS",
    "PUBLISH_SELECTORS",
]
