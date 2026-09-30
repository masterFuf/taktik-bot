"""The Instagram language switch accepts a bare "fr", as the TikTok one does: the Lab and a
caller asking for French should not have to know the country code."""

from taktik.core.social_media.instagram.ui.selectors.flows.settings import APP_LANGUAGE_NATIVE_NAMES


def test_a_bare_fr_is_french_from_france():
    assert APP_LANGUAGE_NATIVE_NAMES["fr"] == APP_LANGUAGE_NATIVE_NAMES["fr-FR"] == "Français (France)"
