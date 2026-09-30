"""TikTok shell selectors."""

from taktik.core.social_media.tiktok.ui.selectors.shell.auth import (
    AUTH_SELECTORS,
    COUNTRY_PICKER_SELECTORS,
    LOGOUT_SELECTORS,
    SIGNUP_SELECTORS,
    TIKTOK_PACKAGE,
    AuthSelectors,
    CountryPickerSelectors,
    LogoutSelectors,
    SignupSelectors,
)
from taktik.core.social_media.tiktok.ui.selectors.shell.navigation import NavigationSelectors, NAVIGATION_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.shell.popups import PopupSelectors, POPUP_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.shell.screen_state import DetectionSelectors, DETECTION_SELECTORS

__all__ = [
    "AUTH_SELECTORS",
    "COUNTRY_PICKER_SELECTORS",
    "LOGOUT_SELECTORS",
    "NAVIGATION_SELECTORS",
    "POPUP_SELECTORS",
    "DETECTION_SELECTORS",
    "SIGNUP_SELECTORS",
    "TIKTOK_PACKAGE",
    "AuthSelectors",
    "CountryPickerSelectors",
    "LogoutSelectors",
    "NavigationSelectors",
    "PopupSelectors",
    "DetectionSelectors",
    "SignupSelectors",
]
