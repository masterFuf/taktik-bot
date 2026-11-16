"""A publication that stops half-way backs out to the feed (`leave_publish_flow`).

Left on the editor or the post screen, TikTok lays the banner « Continuer la modification de cette
publication ? » over every screen of the next launch, and a creator's profile then reads as
`unknown`. Seen on TikTok 47.0.3 in French: from the post screen, back goes to the editor, then to
the gallery (the medium still ticked), then to the camera, then to the feed; no question is asked
and no draft is saved.

The screens are real captures (Pixel 6a, TikTok 47.0.3 in French), anonymized: the post screen of
the publication piloted by hand on 2026-09-27; the editor, the gallery and the camera as each back
left them on 2026-11-15; the feed, with and without the banner.
"""

import pytest

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.services.navigation import reset
from taktik.core.social_media.tiktok.services.publish.navigation import (
    PUBLISH_EXIT_BACK_PRESSES,
    leave_publish_flow,
)
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from screen_phone import EXIT_BACKS as BACKS, EXIT_SCREENS as SCREENS, ScreenPhone

@pytest.fixture(autouse=True)
def phone_4703_in_french(monkeypatch):
    monkeypatch.setattr(reset.time, "sleep", lambda _seconds: None)
    apply_version_overrides("tiktok", "47.0.3")
    set_active_locale("fr")
    yield
    set_active_locale(None)
    apply_version_overrides("tiktok", "43.1.4")


class _Log:
    def __init__(self):
        self.lines = []

    def __call__(self, level, message):
        self.lines.append((level, message))


def test_from_the_post_screen_four_backs_reach_the_feed_and_it_stops_there():
    phone = ScreenPhone("post_screen", SCREENS, BACKS)

    assert leave_publish_flow(phone) is True
    assert phone.screen == "feed"
    assert phone.keys == ["back"] * 4
    assert phone.taps == []


@pytest.mark.parametrize("start, backs", [("editor", 3), ("gallery", 2), ("camera", 1), ("feed", 0)])
def test_from_any_screen_of_the_way_only_the_backs_it_needs(start, backs):
    phone = ScreenPhone(start, SCREENS, BACKS)

    assert leave_publish_flow(phone) is True
    assert phone.keys == ["back"] * backs


def test_the_feed_under_the_banner_is_the_feed_too():
    """What TikTok shows when a publication was left open before: the bottom bar is there."""
    phone = ScreenPhone("camera", SCREENS, {("camera", "back"): "feed_under_banner"})

    assert leave_publish_flow(phone) is True
    assert phone.keys == ["back"]


def test_a_screen_that_cannot_be_read_is_never_taken_for_the_feed():
    """The adb link fell at the camera: the feed comes, but no read of it ever succeeds."""
    phone = ScreenPhone("post_screen", SCREENS, BACKS, unreadable=("camera", "feed"))
    log = _Log()

    assert leave_publish_flow(phone, log=log) is False
    assert phone.keys == ["back"] * PUBLISH_EXIT_BACK_PRESSES
    assert log.lines[-1][0] == "error"
    assert "may still be on the publication" in log.lines[-1][1]


def test_a_publication_that_does_not_let_go_stops_at_the_cap():
    phone = ScreenPhone("editor", SCREENS, {})  # back changes nothing

    assert leave_publish_flow(phone) is False
    assert phone.keys == ["back"] * PUBLISH_EXIT_BACK_PRESSES
    assert phone.screen == "editor"


def test_a_back_that_cannot_be_sent_is_said_and_never_raised():
    class _LinkDown(ScreenPhone):
        def press(self, key):
            raise ConnectionError("adb: device offline")

    log = _Log()

    assert leave_publish_flow(_LinkDown("editor", SCREENS, BACKS), log=log) is False
    assert log.lines == [("error", "[exit] the way out of the publication broke off "
                                   "(adb: device offline): TikTok may still be on the publication")]


@pytest.mark.parametrize("screen", ["post_screen", "editor", "gallery", "camera"])
def test_no_screen_of_the_publication_passes_for_the_feed(screen):
    """The arrival is the app's bottom bar; none of the publication's screens shows it."""
    assert not reset._shell_visible(ScreenPhone(screen, SCREENS, {}))
