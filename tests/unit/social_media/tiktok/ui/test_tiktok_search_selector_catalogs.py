from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import SEARCH_SELECTORS


def test_the_precise_row_anchor_comes_first():
    """Order is the contract here, and it used to be the wrong way round.

    Measured on a real Users tab (46.6.3): `@text="@creator"` matches NOTHING — the tab prints
    the handle with no "@" and wrapped in bidi marks — and `contains(@text, "creator")` matches
    SEVEN nodes, because fan accounts carry the searched handle as their DISPLAY name. Whichever
    of those two fired first opened somebody else's profile.

    The row anchored on `tv_username` resolves exactly one row, carrying exactly the handle
    asked for, so it must be tried before either.
    """
    selectors = SEARCH_SELECTORS.user_result_selectors_for_username("creator")

    assert selectors[0] == (
        '//*[contains(@resource-id, ":id/tv_username")][contains(@text, "creator")]'
        '/ancestor::*[@clickable="true"][1]'
    )
    assert selectors[-len(SEARCH_SELECTORS.first_search_result):] == SEARCH_SELECTORS.first_search_result


def test_the_legacy_forms_are_kept_behind_it():
    """They are wrong on 46.6.3 but were right on the version that shipped them: dropping them
    would trade one broken version for another."""
    selectors = SEARCH_SELECTORS.user_result_selectors_for_username("creator")

    assert '//android.widget.TextView[@text="@creator"]' in selectors
    assert '//android.widget.TextView[contains(@text, "creator")]' in selectors
