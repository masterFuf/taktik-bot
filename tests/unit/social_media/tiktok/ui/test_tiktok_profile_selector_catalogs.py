from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS


def test_profile_extraction_visible_probes_live_in_profile_catalog():
    assert PROFILE_SELECTORS.website_text_probe == "http"
    assert PROFILE_SELECTORS.verified_description_probe == "Verified"
    assert PROFILE_SELECTORS.private_text_probe == "private"
