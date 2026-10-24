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
