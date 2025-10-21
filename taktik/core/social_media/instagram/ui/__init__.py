"""
Interface utilisateur d'Instagram.

Ce package contient les sélecteurs UI centralisés et les extracteurs UI
pour interagir avec l'application Instagram.
"""

# Import des sélecteurs centralisés
from .selectors import (
    ButtonSelectors,
    PostSelectors,
    StorySelectors,
    ScrollSelectors,
    ProfileSelectors,
    DirectMessageSelectors,
    NavigationSelectors,
    DebugSelectors,
    PopupSelectors,
    # Instances prédéfinies
    BUTTON_SELECTORS,
    POST_SELECTORS,
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
    'PostSelectors',
    'StorySelectors',
    'ScrollSelectors',
    'ProfileSelectors',
    'DirectMessageSelectors',
    'NavigationSelectors',
    'DebugSelectors',
    'PopupSelectors',
    # Instances prédéfinies
    'BUTTON_SELECTORS',
    'POST_SELECTORS',
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
