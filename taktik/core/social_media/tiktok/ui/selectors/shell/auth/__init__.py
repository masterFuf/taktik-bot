"""TikTok auth selector catalogs grouped by flow."""

from .country_picker import CountryPickerSelectors, COUNTRY_PICKER_SELECTORS
from .login import TIKTOK_PACKAGE, AuthSelectors, AUTH_SELECTORS
from .logout import LogoutSelectors, LOGOUT_SELECTORS
from .signup import SignupSelectors, SIGNUP_SELECTORS

__all__ = [
    "AUTH_SELECTORS",
    "COUNTRY_PICKER_SELECTORS",
    "LOGOUT_SELECTORS",
    "SIGNUP_SELECTORS",
    "TIKTOK_PACKAGE",
    "AuthSelectors",
    "CountryPickerSelectors",
    "LogoutSelectors",
    "SignupSelectors",
]
