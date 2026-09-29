"""Instagram shell selectors.

Owns selectors related to authentication, global popups, screen-state
recognition, text entry, and blocking modal pages.
"""

from taktik.core.social_media.instagram.ui.selectors.shell.auth import AuthSelectors, AUTH_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.blocking_states import ProblematicPageSelectors, PROBLEMATIC_PAGE_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import ButtonSelectors, BUTTON_SELECTORS, NavigationSelectors, NAVIGATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.popups import PopupSelectors, POPUP_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DetectionSelectors, DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.text_input import TextInputSelectors, TEXT_INPUT_SELECTORS

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
