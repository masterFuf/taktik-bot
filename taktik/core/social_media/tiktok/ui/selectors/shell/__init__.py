"""TikTok shell selectors."""

from .auth import (
    ACCOUNT_SWITCH_SELECTORS,
    AUTH_SELECTORS,
    COUNTRY_PICKER_SELECTORS,
    LOGOUT_SELECTORS,
    SIGNUP_SELECTORS,
    TIKTOK_PACKAGE,
    AuthSelectors,
    AccountSwitchSelectors,
    CountryPickerSelectors,
    LogoutSelectors,
    SignupSelectors,
)
from .navigation import NavigationSelectors, NAVIGATION_SELECTORS
from .popups import PopupSelectors, POPUP_SELECTORS
from .screen_state import DetectionSelectors, DETECTION_SELECTORS

__all__ = [
    "ACCOUNT_SWITCH_SELECTORS",
    "AUTH_SELECTORS",
    "COUNTRY_PICKER_SELECTORS",
    "LOGOUT_SELECTORS",
    "NAVIGATION_SELECTORS",
    "POPUP_SELECTORS",
    "DETECTION_SELECTORS",
    "SIGNUP_SELECTORS",
    "TIKTOK_PACKAGE",
    "AuthSelectors",
    "AccountSwitchSelectors",
    "CountryPickerSelectors",
    "LogoutSelectors",
    "NavigationSelectors",
    "PopupSelectors",
    "DetectionSelectors",
    "SignupSelectors",
]
