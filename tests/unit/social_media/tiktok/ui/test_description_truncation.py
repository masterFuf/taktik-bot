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


def test_a_cut_caption_is_tapped_open_in_french_as_in_english(locale):
    """Proven on 47.0.3 in French (Pixel 6a, 2026-11-20): the tap at the start of the first line
    opened the caption, and the one that left the video was brought back (test_caption_tap.py)."""
    from taktik.core.social_media.tiktok.ui.labels import is_expandable_description

    locale("fr")
    assert is_expandable_description("Deux mots #tag … plus")
    assert not is_expandable_description("Two words #tag …more")
    locale("en")
    assert is_expandable_description("Two words #tag …more")


def _caption_of(name):
    """The text of the caption node (`id/desc`) of a real capture."""
    from taktik.core.shared.device.ui_dump import iter_widgets, parse_ui_dump
    from unit.paths import CORE

    root = parse_ui_dump((CORE / "tests/unit/social_media/tiktok/fixtures" / name).read_text(encoding="utf-8"))
    return next(node.get("text") for node in iter_widgets(root) if (node.get("resource-id") or "").endswith(":id/desc"))


@pytest.mark.parametrize("name", ["tt4703_fr_caption_cut_joined.xml", "tt4703_fr_caption_cut_translate_link.xml"])
def test_a_47_cut_caption_is_recognised_and_read_without_its_tail(locale, name):
    """TikTok 47.0.3 in French (Pixel 6a, 2026-11-20) writes a word joiner (U+2060) before « plus »,
    and on some videos « | Voir la traduction » after it, in the caption's own text: the cut was
    never seen, and the caption went on carrying « plus | Voir la traduction »."""
    from taktik.core.social_media.tiktok.actions.atomic.detection.video_detector import _parse_description
    from taktik.core.social_media.tiktok.ui.labels import caption_as_displayed, strip_more_suffix

    locale("fr")
    caption = _caption_of(name)

    assert is_truncated_description(caption)
    for read in (strip_more_suffix(caption), _parse_description(caption)["description_text"]):
        assert "plus" not in read[-6:] and "traduction" not in read and "⁠" not in read
    assert caption_as_displayed(caption).endswith("…plus")
