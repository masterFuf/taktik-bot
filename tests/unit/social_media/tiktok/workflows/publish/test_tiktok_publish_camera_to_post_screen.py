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
