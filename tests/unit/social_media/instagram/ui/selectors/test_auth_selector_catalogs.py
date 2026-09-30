from taktik.core.social_media.instagram.ui.selectors.shell.auth import AUTH_SELECTORS


def test_auth_clickable_visible_debug_selector_is_catalog_owned():
    assert (
        AUTH_SELECTORS.clickable_visible_elements
        == '//*[@clickable="true" and @visible-to-user="true"]'
    )
