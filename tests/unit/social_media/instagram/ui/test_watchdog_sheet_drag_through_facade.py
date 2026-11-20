"""The watchdog's "swipe the sheet down" recovery drags through the facade it is given.

It is built on a device facade (the Lab's workflow bench hands it one) and called
`swipe(x1, y1, x2, y2, duration=0.3)`, the raw uiautomator2 signature: on the facade the call raised
every time, and only a silent fallback to the raw device moved the sheet, by a two-point swipe the
bottom sheet reads as a fling. Found while fixing the same call in the likers popup reader
(`post.read_likers`, Pixel 6 Pro, Instagram 410, 2026-10-24).

The screen is a real dump, anonymized: the likers sheet of a post (Instagram 410 in French, Pixel 3a).
"""

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.ui.watchdog as watchdog_module
from taktik.core.shared.device.facade import BaseDeviceFacade
from taktik.core.social_media.instagram.ui.watchdog import WorkflowWatchdog
from unit.paths import CORE

LIKERS_SHEET = (CORE / "tests/unit/social_media/instagram/fixtures/ig410_fr_likers_sheet.xml").read_text(
    encoding="utf-8"
)
WIDTH, HEIGHT = 1080, 2220


class _Phone:
    wait_timeout = 0.0

    def __init__(self):
        self.xpath = XPathEntry(self)
        self.swipes = []
        self.paths = []

    def dump_hierarchy(self, *_a, **_k):
        return LIKERS_SHEET

    @property
    def info(self):
        return {"displayWidth": WIDTH, "displayHeight": HEIGHT}

    def window_size(self):
        return WIDTH, HEIGHT

    def swipe_points(self, points, _duration):
        self.paths.append([tuple(point) for point in points])

    def swipe(self, *args, **kwargs):
        self.swipes.append((args, kwargs))


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    monkeypatch.setattr(watchdog_module.time, "sleep", lambda *_: None)


def test_the_sheet_is_dragged_down_through_the_facade_without_a_fallback():
    phone = _Phone()
    watchdog = WorkflowWatchdog(BaseDeviceFacade(phone))

    watchdog._attempt_recovery({"recovery_actions": ["swipe_down"], "overlay": "bottom_sheet"})

    assert phone.swipes == []  # no two-point swipe reached the raw device
    assert len(phone.paths) == 1
    (start_x, start_y), (end_x, end_y) = phone.paths[0][0], phone.paths[0][-1]
    assert end_y > start_y  # the finger goes down, carrying the sheet
    assert len(phone.paths[0]) > 2  # a tracked drag, not a fling


# The Lab bench's watchdog closes a sheet with the project's own gestures (question 2 of the sheet
# lot, 2026-10-25): its drag started at 60 % of the screen, on the sheet's rows, and its tap at a
# quarter of the screen, on an expanded sheet's own content. Real captures, anonymized: a profile's
# options sheet over that profile, and the comments sheet expanded to the top (410, English).

from unit.social_media.instagram.actions.atomic.interaction.sheet_phone import (  # noqa: E402
    SheetPhone, assert_starts_at_the_grab_bar, capture)
from taktik.core.social_media.instagram.actions.atomic.interaction.bottom_sheet import (  # noqa: E402
    find_drag_handle)

OPTIONS_SHEET = capture("ig410_en_profile_options_sheet.xml")
PROFILE_BEHIND = capture("ig410_en_profile_following.xml")
COMMENT_SHEET_EXPANDED = capture("ig410_en_comment_sheet.xml")


def test_the_watchdog_drags_a_sheet_from_its_grab_bar_until_it_is_gone():
    phone = SheetPhone(OPTIONS_SHEET, after=PROFILE_BEHIND)
    facade = BaseDeviceFacade(phone)
    grab_bar = find_drag_handle(facade)

    recovered = WorkflowWatchdog(facade)._attempt_recovery(
        {"recovery_actions": ["swipe_down"], "overlay": "dimmed_bottom_sheet"})

    assert recovered is True
    drags = [g for g in phone.gestures if g[0] == "drag"]
    assert len(drags) == 1, phone.gestures
    assert_starts_at_the_grab_bar(drags[0][1][0], (grab_bar["x"], grab_bar["y"]), phone.height)


def test_the_watchdog_taps_above_a_sheet_that_leaves_room():
    phone = SheetPhone(OPTIONS_SHEET, after=PROFILE_BEHIND)

    recovered = WorkflowWatchdog(BaseDeviceFacade(phone))._attempt_recovery(
        {"recovery_actions": ["tap_outside"], "overlay": "dimmed_bottom_sheet"})

    assert recovered is True
    (kind, _x, y), = phone.gestures
    assert kind == "click" and 0.12 * phone.height <= y < 609  # above the sheet, below the shade zone


def test_the_watchdog_never_taps_into_an_expanded_sheet():
    phone = SheetPhone(COMMENT_SHEET_EXPANDED, after=COMMENT_SHEET_EXPANDED)

    recovered = WorkflowWatchdog(BaseDeviceFacade(phone))._attempt_recovery(
        {"recovery_actions": ["tap_outside"], "overlay": "dimmed_bottom_sheet"})

    assert recovered is False
    assert phone.gestures == []
