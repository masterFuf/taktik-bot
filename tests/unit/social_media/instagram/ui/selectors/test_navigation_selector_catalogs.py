from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS


def test_search_result_selectors_for_username_use_navigation_catalog_ids():
    selectors = NAVIGATION_SELECTORS.search_result_selectors_for_username("target_user")

    assert selectors[0] == (
        '//*[contains(@resource-id, "com.instagram.android:id/row_search_user_container")]'
        '[.//*[contains(@resource-id, "com.instagram.android:id/row_search_user_username") '
        'and @text="target_user"]]'
    )
    assert selectors[-1] == (
        '//*[@clickable="true"]'
        '[.//*[contains(@resource-id, "com.instagram.android:id/row_search_user_username") '
        'and @text="target_user"]]'
    )


def test_hashtag_selectors_are_built_from_navigation_catalog():
    selectors = NAVIGATION_SELECTORS.hashtag_result_selectors("growth")

    assert selectors[:3] == [
        '//android.widget.TextView[@text="#growth"]',
        '//*[contains(@text, "#growth")]',
        '//*[contains(@content-desc, "#growth")]',
    ]
    assert NAVIGATION_SELECTORS.hashtag_text_contains("growth") == '//*[contains(@text, "#growth")]'
