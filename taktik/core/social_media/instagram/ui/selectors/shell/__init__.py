"""Instagram shell selectors.

Owns selectors related to authentication, global popups, screen-state
recognition, text entry, and blocking modal pages.
"""

from .auth import AuthSelectors, AUTH_SELECTORS
from .blocking_states import ProblematicPageSelectors, PROBLEMATIC_PAGE_SELECTORS
from .navigation import ButtonSelectors, BUTTON_SELECTORS, NavigationSelectors, NAVIGATION_SELECTORS
from .popups import PopupSelectors, POPUP_SELECTORS
from .screen_state import DetectionSelectors, DETECTION_SELECTORS
from .text_input import TextInputSelectors, TEXT_INPUT_SELECTORS

__all__ = [
    "AUTH_SELECTORS",
    "BUTTON_SELECTORS",
    "DETECTION_SELECTORS",
    "NAVIGATION_SELECTORS",
    "POPUP_SELECTORS",
    "PROBLEMATIC_PAGE_SELECTORS",
    "TEXT_INPUT_SELECTORS",
    "AuthSelectors",
    "ButtonSelectors",
    "DetectionSelectors",
    "NavigationSelectors",
    "PopupSelectors",
    "ProblematicPageSelectors",
    "TextInputSelectors",
]
