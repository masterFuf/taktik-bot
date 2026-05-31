from taktik.core.social_media.instagram.ui.selectors.support import WATCHDOG_SELECTORS


def test_watchdog_overlay_signatures_are_catalog_owned():
    names = {signature["name"] for signature in WATCHDOG_SELECTORS.overlay_signatures}

    assert "comments_popup" in names
    assert "rate_limit_popup" in names
    assert "login_required" in names


def test_watchdog_clickable_text_selector_builds_recovery_xpath():
    assert WATCHDOG_SELECTORS.clickable_text_selector("OK") == '//*[@text="OK" and @clickable="true"]'
