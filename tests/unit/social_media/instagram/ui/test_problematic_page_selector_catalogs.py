from taktik.core.social_media.instagram.ui.selectors.shell.blocking_states import (
    PROBLEMATIC_PAGE_SELECTORS,
)


def test_problematic_page_permission_allow_selectors_are_catalog_owned():
    assert PROBLEMATIC_PAGE_SELECTORS.allow_permission_button_selectors == [
        {"resourceId": "com.android.packageinstaller:id/permission_allow_button"},
        {"text": "AUTORISER"},
        {"text": "ALLOW"},
        {"text": "Autoriser"},
        {"text": "Allow"},
    ]
