"""
Interface utilisateur d'Instagram.

Ce package contient les sélecteurs UI centralisés et les extracteurs UI
pour interagir avec l'application Instagram.
"""

# Import des sélecteurs centralisés
from .selectors import (
    ButtonSelectors,
    PostCommentsSelectors,
    PostDetailSelectors,
    PostGridSelectors,
    PostLikersSelectors,
    PostSelectors,
    PostReelsSelectors,
    PostShareSheetSelectors,
    StorySelectors,
    ScrollSelectors,
    ProfileSelectors,
    DirectMessageSelectors,
    NavigationSelectors,
    DebugSelectors,
    PopupSelectors,
    # Instances prédéfinies
    BUTTON_SELECTORS,
    POST_COMMENTS_SELECTORS,
    POST_DETAIL_SELECTORS,
    POST_GRID_SELECTORS,
    POST_LIKERS_SELECTORS,
    POST_SELECTORS,
    POST_REELS_SELECTORS,
    POST_SHARE_SHEET_SELECTORS,
    STORY_SELECTORS,
    SCROLL_SELECTORS,
    PROFILE_SELECTORS,
    DM_SELECTORS,
    NAVIGATION_SELECTORS,
    DEBUG_SELECTORS,
    POPUP_SELECTORS
)

# Import des extracteurs UI
from .extractors import (
    InstagramUIExtractors,
    parse_instagram_number
)

__all__ = [
    # Classes de sélecteurs
    'ButtonSelectors',
    'PostCommentsSelectors',
    'PostDetailSelectors',
    'PostGridSelectors',
    'PostLikersSelectors',
    'PostSelectors',
    'PostReelsSelectors',
    'PostShareSheetSelectors',
    'StorySelectors',
    'ScrollSelectors',
    'ProfileSelectors',
    'DirectMessageSelectors',
    'NavigationSelectors',
    'DebugSelectors',
    'PopupSelectors',
    # Instances prédéfinies
    'BUTTON_SELECTORS',
    'POST_COMMENTS_SELECTORS',
    'POST_DETAIL_SELECTORS',
    'POST_GRID_SELECTORS',
    'POST_LIKERS_SELECTORS',
    'POST_SELECTORS',
    'POST_REELS_SELECTORS',
    'POST_SHARE_SHEET_SELECTORS',
    'STORY_SELECTORS',
    'SCROLL_SELECTORS',
    'PROFILE_SELECTORS',
    'DM_SELECTORS',
    'NAVIGATION_SELECTORS',
    'DEBUG_SELECTORS',
    'POPUP_SELECTORS',
    # Extracteurs UI
    'InstagramUIExtractors',
    'parse_instagram_number'
]
