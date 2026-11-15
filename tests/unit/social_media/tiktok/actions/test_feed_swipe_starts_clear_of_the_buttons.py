"""The finger of a feed advance goes down clear of the video's buttons.

The touch-down of the For You advance is drawn from real human swipes, x up to 94 % of the width:
it could land on the rail (like, comment, favourite, share, sound), the author's avatar, its follow
button, the author's name or the caption. The shared gesture engine can move a touch-down off
the controls a platform names (`_prepare_gesture_path`); Instagram names them, TikTok did not, and
the facade's gesture host handed the engine no hook. Now the TikTok facade names the controls of
the photo, read by the production selectors, and the advance asks for the guard.

The screens are real captures, anonymized: a For You video of the base version (43.1.4, French).
"""

import random
import time

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.actions.atomic.scroll.scroll_actions import ScrollActions
from taktik.core.social_media.tiktok.actions.base.device_facade import DeviceFacade
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.gesture import VIDEO_GESTURE_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
VIDEO = (FIXTURES / "tt4314_fr_for_you_video.xml").read_text(encoding="utf-8")
WIDTH, HEIGHT = 1080, 2400

#: Controls of that capture (left, top, right, bottom), read node by node.
LIKE = (912, 1414, 1080, 1572)
COMMENT = (912, 1572, 1080, 1730)
AUTHOR = (32, 1996, 273, 2054)
CAPTION = (32, 2072, 870, 2123)
ADVANCES = 100


def _inside(point, box):
    (x, y), (left, top, right, bottom) = point, box
    return left <= x <= right and top <= y <= bottom


class _Phone:
    """uiautomator2 as the gestures reach it: one still screen, the swipes it injects."""

    wait_timeout = 0.2
    info = {"displayWidth": WIDTH, "displayHeight": HEIGHT}

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)
        self.starts = []

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def window_size(self):
        return WIDTH, HEIGHT

    def swipe(self, sx, sy, ex, ey, duration=None):
        self.starts.append((sx, sy))

    def swipe_points(self, points, duration=None):
        self.starts.append(tuple(points[0]))


@pytest.fixture(autouse=True)
def french(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


class _Style:
    """The session's choice of gesture for the advance, fixed: a flick, or a drag."""

    def __init__(self, mode):
        self.mode = mode

    def choose_scroll_mode(self, context):
        return {"mode": self.mode}


def test_the_zones_are_the_controls_of_the_photo():
    zones = DeviceFacade(_Phone(VIDEO))._gesture_start_exclusion_bounds()
    for control in (LIKE, COMMENT, AUTHOR, CAPTION):
        assert control in zones
    # The video itself is no control: nothing covers the middle of the screen.
    assert not any(_inside((WIDTH // 2, HEIGHT // 2), zone) for zone in zones)


@pytest.mark.parametrize("mode", ["flick", "drag"])
def test_a_hundred_feed_advances_start_on_none_of_them(mode):
    phone = _Phone(VIDEO)
    facade = DeviceFacade(phone)
    zones = facade._gesture_start_exclusion_bounds()
    scroll = ScrollActions(facade)
    scroll.behavior_state = _Style(mode)
    random.seed(2026)
    sources = set()
    for _ in range(ADVANCES):
        scroll._swipe_to_next_video()
        sources.add(facade.last_gesture_start()["source"])
    assert len(phone.starts) == ADVANCES
    on_a_control = [start for start in phone.starts if any(_inside(start, zone) for zone in zones)]
    assert on_a_control == []
    assert sources <= {"ui_bounds", "ui_bounds_clear"}


def test_an_unreadable_screen_starts_in_the_band_of_the_catalogue():
    phone = _Phone("")
    facade = DeviceFacade(phone)
    scroll = ScrollActions(facade)
    random.seed(7)
    low, high = VIDEO_GESTURE_SELECTORS.gesture_fallback_safe_x_band
    for _ in range(20):
        scroll._swipe_to_next_video()
        assert facade.last_gesture_start()["source"] == "fallback_band"
    assert all(low * WIDTH - 1 <= x <= high * WIDTH + 1 for x, _y in phone.starts)


def test_a_list_scroll_keeps_its_sampled_start():
    """Only the feed advance asks for the guard: a list (followers, search) is no video."""
    phone = _Phone(VIDEO)
    facade = DeviceFacade(phone)
    facade.swipe_up()
    assert facade.last_gesture_start()["source"] == "none"
