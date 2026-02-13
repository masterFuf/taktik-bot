"""Sélecteurs UI pour TikTok — organisés par domaine.

Chaque domaine a son propre fichier. Ce barrel re-exporte tout
pour que les imports existants continuent de fonctionner:

    from ...ui.selectors import NAVIGATION_SELECTORS, VIDEO_SELECTORS
"""

from .auth import AuthSelectors, AUTH_SELECTORS, TIKTOK_PACKAGE
from .navigation import NavigationSelectors, NAVIGATION_SELECTORS
from .profile import ProfileSelectors, PROFILE_SELECTORS
from .video import VideoSelectors, VIDEO_SELECTORS
from .comment import CommentSelectors, COMMENT_SELECTORS
from .search import SearchSelectors, SEARCH_SELECTORS
from .inbox import InboxSelectors, INBOX_SELECTORS
from .conversation import ConversationSelectors, CONVERSATION_SELECTORS
from .popup import PopupSelectors, POPUP_SELECTORS
from .scroll import ScrollSelectors, SCROLL_SELECTORS
from .detection import DetectionSelectors, DETECTION_SELECTORS
from .followers import FollowersSelectors, FOLLOWERS_SELECTORS

__all__ = [
    'TIKTOK_PACKAGE',
    'AuthSelectors',
    'NavigationSelectors',
    'ProfileSelectors',
    'VideoSelectors',
    'InboxSelectors',
    'ConversationSelectors',
    'CommentSelectors',
    'SearchSelectors',
    'PopupSelectors',
    'ScrollSelectors',
    'DetectionSelectors',
    'FollowersSelectors',
    'AUTH_SELECTORS',
    'NAVIGATION_SELECTORS',
    'PROFILE_SELECTORS',
    'VIDEO_SELECTORS',
    'COMMENT_SELECTORS',
    'SEARCH_SELECTORS',
    'INBOX_SELECTORS',
    'CONVERSATION_SELECTORS',
    'POPUP_SELECTORS',
    'SCROLL_SELECTORS',
    'DETECTION_SELECTORS',
    'FOLLOWERS_SELECTORS',
]
