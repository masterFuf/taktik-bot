from taktik.core.social_media.tiktok.ui.selectors.auth import (
    AUTH_SELECTORS,
    COUNTRY_PICKER_SELECTORS,
    LOGOUT_SELECTORS,
    SIGNUP_SELECTORS,
)
from taktik.core.social_media.tiktok.ui.selectors.shell.auth.login import AUTH_SELECTORS as LOGIN_AUTH_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.shell.auth.country_picker import (
    COUNTRY_PICKER_SELECTORS as PACKAGE_COUNTRY_PICKER_SELECTORS,
)
from taktik.core.social_media.tiktok.ui.selectors.shell.auth.logout import (
    LOGOUT_SELECTORS as PACKAGE_LOGOUT_SELECTORS,
)
from taktik.core.social_media.tiktok.ui.selectors.shell.auth.signup import (
    SIGNUP_SELECTORS as PACKAGE_SIGNUP_SELECTORS,
)


def test_auth_shim_points_to_login_catalog():
    assert AUTH_SELECTORS is LOGIN_AUTH_SELECTORS


def test_auth_shim_points_to_signup_catalog():
    assert SIGNUP_SELECTORS is PACKAGE_SIGNUP_SELECTORS


def test_auth_shim_points_to_country_picker_catalog():
    assert COUNTRY_PICKER_SELECTORS is PACKAGE_COUNTRY_PICKER_SELECTORS


def test_auth_shim_points_to_logout_catalog():
    assert LOGOUT_SELECTORS is PACKAGE_LOGOUT_SELECTORS
