"""From the camera to the post screen of TikTok 47.0.3, on the real screens of one publication.

The screens are the anonymized dumps of the publication piloted by hand on 2026-09-27 (Pixel 6a,
French); `ScreenPhone` moves between them as that phone did, tap by tap, and hit-tests every tap
like a finger. The production functions run on it with the selectors the connection patches for
47.0.3; they may tap only the nodes the hand tapped that day.
"""

import pytest
from screen_phone import ScreenPhone

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.services.publish import navigation
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale

SCREENS = {
    "camera": "tt4703_fr_publish_camera.xml",
    "gallery": "tt4703_fr_publish_gallery.xml",
    "gallery_ticked": "tt4703_fr_publish_gallery_selected.xml",
    "editor_with_sound": "tt4703_fr_publish_editor_sound.xml",
    "editor_without_sound": "tt4703_fr_publish_editor_no_sound.xml",
    "post_screen": "tt4703_fr_publish_post_screen.xml",
}
# The gestures of 2026-09-27, one move each.
MOVES = {
    ("camera", "upload_hot_area"): "gallery",
    ("gallery", "l34"): "gallery_ticked",
    ("gallery_ticked", "xyk"): "editor_with_sound",
    ("editor_with_sound", "e1d"): "editor_without_sound",
    ("editor_without_sound", "q03"): "post_screen",
}


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


def _phone(screen="camera"):
    return ScreenPhone(screen, SCREENS, MOVES)


def test_on_47_0_3_the_camera_opens_the_gallery_by_its_entry(on_47_0_3):
    phone = _phone()

    assert navigation.tap_upload_button(phone)
    assert phone.tapped() == ["upload_hot_area"]
    assert phone.screen == "gallery"


def test_where_no_selector_knows_the_entry_nothing_is_tapped():
    """The baseline catalogue on the 47.0.3 camera: the run of 2026-09-27 tapped the effects
    carousel four times here, and an effect with its sound stuck to the camera."""
    phone = _phone()

    assert not navigation.tap_upload_button(phone)
    assert phone.taps == []


def test_on_47_0_3_the_production_steps_go_from_the_camera_to_the_post_screen(on_47_0_3, monkeypatch):
    """Each step of the workflow, in its order, on the real screens: every tap on the node the hand
    tapped that day, the sound off before the editor's Next."""
    monkeypatch.setattr(navigation, "handle_permission_dialog", lambda *_args, **_kwargs: False)
    phone = _phone()
    no_sleep = lambda _seconds: None  # noqa: E731

    assert navigation.tap_upload_button(phone)
    assert navigation.ensure_gallery_picker_open(phone, "device-1", sleep=no_sleep)
    assert navigation.select_first_gallery_item(phone)
    assert navigation.advance_to_post_screen(phone, sleep=no_sleep) == navigation.POST_SCREEN_REACHED

    assert [(tap.rid, tap.bounds) for tap in phone.taps] == [
        ("upload_hot_area", "[0,2118][210,2314]"),
        ("l34", "[280,397][343,460]"),  # the box of the newest cell, top left
        ("xyk", "[550,2179][1048,2295]"),  # Suivant (1)
        ("e1d", "[703,203][801,319]"),  # the cross of the sound TikTok attached
        ("q03", "[545,2192][1048,2308]"),  # Suivant, never Ta Story
    ]
    assert phone.screen == "post_screen"


def test_where_no_selector_knows_the_gallery_nothing_is_tapped():
    """The baseline catalogue on the 47.0.3 gallery: the grid fallback tapped the thumbnail of the
    first cell, not its selection box, and reported the medium selected."""
    phone = _phone("gallery")

    assert not navigation.select_first_gallery_item(phone)
    assert phone.taps == []
