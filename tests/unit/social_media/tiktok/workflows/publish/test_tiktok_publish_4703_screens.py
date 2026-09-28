"""The publication screens of TikTok 47.0.3, read by the catalogue as the connection patches it.

Real screens, anonymized (Pixel 6a, 1080x2400, TikTok 47.0.3 in French, one publication piloted by
hand node by node on 2026-09-27): the camera, the gallery, the gallery with its first cell ticked,
the editor with the sound TikTok attached on its own, the same editor once that sound is off, and
the post screen. Beside them, the camera and the gallery of 43.1.4 in French (the baseline, a
production publish run of 2026-06-18), which the 47.0.3 entries must keep finding: an override
replaces its list, so it carries the baseline entries along.

Each selector list is read the way `find_element` reads it: the first xpath that matches wins.
"""

from pathlib import Path

import pytest

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.tiktok.ui.selectors.flows.publish import (
    PUBLISH_COMPOSER_SELECTORS,
    PUBLISH_EDITOR_SELECTORS,
    PUBLISH_MEDIA_PICKER_SELECTORS,
)
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale

FIXTURES = Path(__file__).parents[2] / "fixtures"

CAMERA_43_1_4 = "tt4314_fr_publish_camera.xml"
GALLERY_43_1_4 = "tt4314_fr_publish_gallery.xml"
CAMERA = "tt4703_fr_publish_camera.xml"
GALLERY = "tt4703_fr_publish_gallery.xml"
GALLERY_TICKED = "tt4703_fr_publish_gallery_selected.xml"
EDITOR_WITH_SOUND = "tt4703_fr_publish_editor_sound.xml"
EDITOR_WITHOUT_SOUND = "tt4703_fr_publish_editor_no_sound.xml"
POST_SCREEN = "tt4703_fr_publish_post_screen.xml"


def _screen(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _first_match(name: str, xpaths):
    """(resource-id after `:id/`, bounds) of what the first matching xpath finds, or None."""
    tree = parse_ui_dump(_screen(name))
    for xpath in xpaths:
        nodes = tree.xpath(xpath)
        if nodes:
            rid = nodes[0].get("resource-id") or ""
            return rid.split(":id/")[-1], nodes[0].get("bounds")
    return None


def _any_match(name: str, xpaths) -> bool:
    return _first_match(name, xpaths) is not None


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


@pytest.fixture
def on_47_0_3():
    apply_version_overrides("tiktok", "47.0.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")


# --- the camera: the way into the gallery ----------------------------------------------------


def test_the_baseline_finds_no_way_into_the_gallery_on_the_47_0_3_camera():
    """The defect of 2026-09-27: nothing answered, and the coordinate fallback tapped the effects."""
    assert _first_match(CAMERA, PUBLISH_MEDIA_PICKER_SELECTORS.upload_btn) is None


def test_on_47_0_3_the_way_into_the_gallery_is_upload_hot_area(on_47_0_3):
    assert _first_match(CAMERA, PUBLISH_MEDIA_PICKER_SELECTORS.upload_btn) == (
        "upload_hot_area", "[0,2118][210,2314]")


def test_on_47_0_3_the_43_1_4_camera_still_opens_its_gallery(on_47_0_3):
    assert _first_match(CAMERA_43_1_4, PUBLISH_MEDIA_PICKER_SELECTORS.upload_btn)[0] == "ymg"


# --- the gallery: seen, and its newest cell ticked --------------------------------------------


def test_the_baseline_does_not_see_the_47_0_3_gallery():
    assert not _any_match(GALLERY, PUBLISH_MEDIA_PICKER_SELECTORS.gallery_first_item)


def test_on_47_0_3_the_first_item_is_the_box_of_the_top_left_cell(on_47_0_3):
    assert _first_match(GALLERY, PUBLISH_MEDIA_PICKER_SELECTORS.gallery_first_item) == (
        "l34", "[280,397][343,460]")


def test_on_47_0_3_the_gallery_is_told_from_the_camera_under_it(on_47_0_3):
    """`is_gallery_picker_open` asks these xpaths first: the camera answers none of them."""
    assert _any_match(GALLERY, PUBLISH_MEDIA_PICKER_SELECTORS.gallery_first_item)
    assert not _any_match(CAMERA, PUBLISH_MEDIA_PICKER_SELECTORS.gallery_first_item)


def test_on_47_0_3_the_43_1_4_gallery_is_still_seen(on_47_0_3):
    assert _first_match(GALLERY_43_1_4, PUBLISH_MEDIA_PICKER_SELECTORS.gallery_first_item)[0] == "mub"


# --- Next, from the gallery and from the editor ------------------------------------------------


def test_on_47_0_3_next_is_the_gallery_button_once_a_cell_is_ticked(on_47_0_3):
    assert _first_match(GALLERY_TICKED, PUBLISH_MEDIA_PICKER_SELECTORS.next_btn) == (
        "xyk", "[550,2179][1048,2295]")


def test_on_47_0_3_next_on_the_editor_is_q03_never_the_story_shortcut(on_47_0_3):
    for editor in (EDITOR_WITH_SOUND, EDITOR_WITHOUT_SOUND):
        assert _first_match(editor, PUBLISH_MEDIA_PICKER_SELECTORS.next_btn) == (
            "q03", "[545,2192][1048,2308]")
        tree = parse_ui_dump(_screen(editor))
        story = tree.xpath('//*[contains(@resource-id, ":id/tq4")]')[0]
        for xpath in PUBLISH_MEDIA_PICKER_SELECTORS.next_btn:
            for node in tree.xpath(xpath):
                assert node is not story and story not in node.iterancestors(), xpath


# --- the editor: the sound TikTok attached -----------------------------------------------------


def test_the_baseline_knows_no_sound_chip():
    """Never captured on 43.1.4: no baseline entry, and nothing is guessed."""
    assert PUBLISH_EDITOR_SELECTORS.sound_chip == []
    assert PUBLISH_EDITOR_SELECTORS.sound_remove_btn == []


def test_on_47_0_3_the_cross_shows_only_while_a_sound_is_on_the_video(on_47_0_3):
    assert _first_match(EDITOR_WITH_SOUND, PUBLISH_EDITOR_SELECTORS.sound_remove_btn) == (
        "e1d", "[703,203][801,319]")
    assert not _any_match(EDITOR_WITHOUT_SOUND, PUBLISH_EDITOR_SELECTORS.sound_remove_btn)


def test_on_47_0_3_the_chip_is_on_both_editors_and_reads_the_invitation_once_empty(on_47_0_3):
    assert _any_match(EDITOR_WITH_SOUND, PUBLISH_EDITOR_SELECTORS.sound_chip)
    label = parse_ui_dump(_screen(EDITOR_WITHOUT_SOUND)).xpath(PUBLISH_EDITOR_SELECTORS.sound_chip[0])[0]
    assert label.get("text") == "Ajouter un son"


# --- the post screen ---------------------------------------------------------------------------


def test_on_47_0_3_the_post_screen_names_its_field_and_its_button_first(on_47_0_3):
    """By their ids, at the head of their lists: the baseline ids are absent, and `find_element`
    waits on each absent xpath (five seconds apiece before the Publier button was reached)."""
    assert _first_match(POST_SCREEN, PUBLISH_COMPOSER_SELECTORS.caption_input[:1]) == (
        "h8e", "[42,270][673,677]")
    assert _first_match(POST_SCREEN, PUBLISH_COMPOSER_SELECTORS.post_btn[:1]) == (
        "tiq", "[550,2179][1048,2305]")


def test_on_47_0_3_the_post_screen_is_told_from_the_editor(on_47_0_3):
    """By the French label of the field ("Ajouter une description"), the marker of the locale."""
    assert PUBLISH_COMPOSER_SELECTORS.has_post_screen_marker(_screen(POST_SCREEN))
    for editor in (EDITOR_WITH_SOUND, EDITOR_WITHOUT_SOUND):
        assert not PUBLISH_COMPOSER_SELECTORS.has_post_screen_marker(_screen(editor))
