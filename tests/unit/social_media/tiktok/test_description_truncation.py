"""A truncated caption ends with an ellipsis and the locale's "more" word. The French one was
never recognised: the check looked for the English word only, so no French caption was expanded."""

import pytest

from taktik.core.social_media.tiktok.ui.labels import is_truncated_description
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale


@pytest.fixture
def locale():
    yield set_active_locale
    set_active_locale(None)


@pytest.mark.parametrize("caption", ["Deux mots… plus", "Deux mots…plus", "fin... plus"])
def test_a_french_truncated_caption_is_recognised(locale, caption):
    locale("fr")
    assert is_truncated_description(caption)


@pytest.mark.parametrize("caption", ["Encore plus", "Un peu plus !", "texte…more", ""])
def test_a_french_caption_that_is_not_cut_stays_as_is(locale, caption):
    locale("fr")
    assert not is_truncated_description(caption)


def test_the_english_caption_keeps_working(locale):
    locale("en")
    assert is_truncated_description("some text…more")
    assert not is_truncated_description("no more")


def test_the_cut_marker_is_removed_from_the_parsed_caption(locale):
    from taktik.core.social_media.tiktok.actions.atomic.detection.video_detector import _parse_description

    locale("fr")
    assert _parse_description("Le secret #bio … plus")["description_text"] == "Le secret"
    locale("en")
    assert _parse_description("The secret #bio …more")["description_text"] == "The secret"
