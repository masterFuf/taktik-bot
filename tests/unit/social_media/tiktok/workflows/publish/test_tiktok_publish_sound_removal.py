"""The sound TikTok attaches on its own to an imported video is taken off before the post screen.

Decision of 2026-09-27: a video the bot publishes carries no third-party music. The screens are the
real editor of TikTok 47.0.3 (French, Pixel 6a) with the sound TikTok attached ("You ..." on the
chip) and the same editor once its cross was tapped by hand ("Ajouter un son", no cross), plus the
gallery drawn over the camera. `ScreenPhone` moves between them as the phone did.
"""

import pytest
from screen_phone import ScreenPhone

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.services.publish import editor_sound, navigation
from taktik.core.social_media.tiktok.services.publish.editor_sound import (
    NO_SOUND,
    SOUND_KEPT,
    SOUND_REMOVED,
    SOUND_UNCHECKED,
    remove_attached_sound,
    sound_removal_is_known,
)
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale

SCREENS = {
    "gallery_ticked": "tt4703_fr_publish_gallery_selected.xml",
    "editor_with_sound": "tt4703_fr_publish_editor_sound.xml",
    "editor_without_sound": "tt4703_fr_publish_editor_no_sound.xml",
    "post_screen": "tt4703_fr_publish_post_screen.xml",
}
MOVES = {
    ("gallery_ticked", "xyk"): "editor_with_sound",
    ("editor_with_sound", "e1d"): "editor_without_sound",
    ("editor_without_sound", "q03"): "post_screen",
    ("editor_with_sound", "q03"): "post_screen",
}
# The cross does nothing: the sound stays.
STUCK_CROSS = {key: screen for key, screen in MOVES.items() if key[1] != "e1d"}


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


class CollectedLog:
    def __init__(self):
        self.lines = []

    def __call__(self, level, message):
        self.lines.append((level, message))

    def levels(self):
        return [level for level, _ in self.lines]


def _no_sleep(_seconds):
    return None


# --- one screen ---------------------------------------------------------------------------------


def test_the_sound_on_the_editor_is_taken_off_and_checked(on_47_0_3):
    phone = ScreenPhone("editor_with_sound", SCREENS, MOVES)
    log = CollectedLog()

    assert remove_attached_sound(phone, sleep=_no_sleep, log=log) == SOUND_REMOVED
    assert [(tap.rid, tap.bounds) for tap in phone.taps] == [("e1d", "[703,203][801,319]")]
    assert phone.screen == "editor_without_sound"
    assert "'Ajouter un son'" in log.lines[-1][1]


def test_a_cross_that_does_nothing_stops_on_a_kept_sound(on_47_0_3):
    phone = ScreenPhone("editor_with_sound", SCREENS, STUCK_CROSS)
    log = CollectedLog()

    assert remove_attached_sound(phone, sleep=_no_sleep, log=log) == SOUND_KEPT
    assert phone.tapped() == ["e1d"] * editor_sound.REMOVE_ATTEMPTS
    assert log.levels()[-1] == "error"


def test_an_editor_without_sound_is_left_as_it_is(on_47_0_3):
    phone = ScreenPhone("editor_without_sound", SCREENS, MOVES)

    assert remove_attached_sound(phone, sleep=_no_sleep) == NO_SOUND
    assert phone.taps == []
    # TikTok may attach its sound a moment late: the editor is read over the settle time.
    assert phone.dumps == round(editor_sound.SETTLE_SECONDS / editor_sound.POLL_SECONDS) + 1


def test_the_camera_chip_under_the_gallery_is_not_the_video_s(on_47_0_3):
    phone = ScreenPhone("gallery_ticked", SCREENS, MOVES)

    assert remove_attached_sound(phone, sleep=_no_sleep) == NO_SOUND
    assert phone.taps == [] and phone.dumps == 1


def test_an_unreadable_screen_is_no_proof_of_silence(on_47_0_3):
    class Unreadable:
        def dump_hierarchy(self, compressed=False):
            raise ConnectionError("uiautomator server gone")

    log = CollectedLog()

    assert remove_attached_sound(Unreadable(), sleep=_no_sleep, log=log) == SOUND_UNCHECKED
    assert "error" in log.levels()


def test_on_the_baseline_the_cross_is_unknown_and_the_screen_is_not_read():
    phone = ScreenPhone("editor_with_sound", SCREENS, MOVES)

    assert not sound_removal_is_known()
    assert remove_attached_sound(phone, sleep=_no_sleep) == NO_SOUND
    assert phone.dumps == 0 and phone.taps == []


# --- the way to the post screen -----------------------------------------------------------------


def test_next_is_tapped_on_the_editor_only_once_the_sound_is_off(on_47_0_3):
    phone = ScreenPhone("gallery_ticked", SCREENS, MOVES)

    assert navigation.advance_to_post_screen(phone, sleep=_no_sleep) == navigation.POST_SCREEN_REACHED
    assert phone.tapped() == ["xyk", "e1d", "q03"]
    assert phone.screen == "post_screen"


def test_a_sound_that_stays_stops_before_next(on_47_0_3):
    phone = ScreenPhone("gallery_ticked", SCREENS, STUCK_CROSS)

    assert navigation.advance_to_post_screen(phone, sleep=_no_sleep) == navigation.SOUND_NOT_REMOVED
    assert "q03" not in phone.tapped()
    assert phone.screen == "editor_with_sound"


def test_a_version_without_the_cross_says_so_once(monkeypatch):
    log = CollectedLog()
    phone = ScreenPhone("post_screen", SCREENS, MOVES)

    assert navigation.advance_to_post_screen(phone, sleep=_no_sleep, log=log) == navigation.POST_SCREEN_REACHED
    assert log.levels() == ["warning"]
