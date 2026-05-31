from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import SEARCH_SELECTORS


def test_user_result_selectors_for_username_include_fallback_result():
    selectors = SEARCH_SELECTORS.user_result_selectors_for_username("creator")

    assert selectors[:2] == [
        '//android.widget.TextView[@text="@creator"]',
        '//android.widget.TextView[contains(@text, "creator")]',
    ]
    assert selectors[2:] == SEARCH_SELECTORS.first_search_result
