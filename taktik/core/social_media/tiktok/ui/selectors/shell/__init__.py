"""TikTok shell selectors."""

from .auth import (
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
from .navigation import NavigationSelectors, NAVIGATION_SELECTORS
from .popups import PopupSelectors, POPUP_SELECTORS
from .screen_state import DetectionSelectors, DETECTION_SELECTORS

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
