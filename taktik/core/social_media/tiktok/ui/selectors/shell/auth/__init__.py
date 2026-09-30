"""TikTok auth selector catalogs grouped by flow."""

from taktik.core.social_media.tiktok.ui.selectors.shell.auth.country_picker import (
    CountryPickerSelectors,
    COUNTRY_PICKER_SELECTORS,
)
from taktik.core.social_media.tiktok.ui.selectors.shell.auth.login import TIKTOK_PACKAGE, AuthSelectors, AUTH_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.shell.auth.logout import LogoutSelectors, LOGOUT_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.shell.auth.signup import SignupSelectors, SIGNUP_SELECTORS

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
