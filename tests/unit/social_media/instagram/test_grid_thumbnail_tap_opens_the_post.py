"""A tap on a profile-grid thumbnail must open the post, every time.

Device case (Pixel 3, Instagram 410.0.0.53.71): `profile.open_first_post` and
`post.return_to_grid_and_reopen` sometimes reported "first post opened=False" although the tap
landed well inside the cell. Measured on the phone, with the DOWN to UP gap read in
`dumpsys input`: the grid turns a touch into its "peek" preview after about 200 ms of contact,
and the release then opens nothing (18 posts out of 18 opened at up to 189 ms, 0 out of 7 from
200 ms). The app sees the requested hold plus the uiautomator2 injection lag (+21 to +49 ms),
and the human tap asked for up to 220 ms: about 2 to 4 % of grid taps crossed the threshold.

The screens are real dumps of that phone, anonymized: a profile and its grid
(`fixtures/ig410_fr_profile_opened_from_search.xml`) and a post opened from a profile grid
(`fixtures/ig410_fr_post_opened_from_grid.xml`).
"""

import random
import time
from functools import lru_cache
from pathlib import Path

import pytest
from loguru import logger

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.actions.business.actions.like.post_navigation import (
    PostNavigationMixin,
)
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post.detail import POST_SELECTORS

# What the phone showed (see the module docstring).
_WORST_LAG_MS = 49.0
_PEEK_MS = 200.0
# uiautomator2's plain click() holds 100 ms on the device side.
_U2_CLICK_HOLD_MS = 100.0

FIXTURES = Path(__file__).parent / "fixtures"
PROFILE_GRID = (FIXTURES / "ig410_fr_profile_opened_from_search.xml").read_text(encoding="utf-8")
POST_VIEW = (FIXTURES / "ig410_fr_post_opened_from_grid.xml").read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def _tree(xml):
    """A whole dump, parsed once: the fake answers hundreds of taps on the same two screens."""
    return parse_ui_dump(xml)


def _bounds(node):
    left_top, right_bottom = node.get("bounds").strip("[]").split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


class _Element:
    def __init__(self, device, node):
        self._device = device
        self.attrib = dict(node.attrib)
        self.bounds = _bounds(node)

    def click(self):
        left, top, right, bottom = self.bounds
        self._device.click((left + right) // 2, (top + bottom) // 2)


class _Selection:
    def __init__(self, device, nodes):
        self._device = device
        self._nodes = nodes

    @property
    def exists(self):
        return bool(self._nodes)

    def all(self):
        return [_Element(self._device, node) for node in self._nodes]


class _Instagram410Grid:
    """Raw uiautomator2 stand-in replaying the dumps, with the touch behaviour measured on device."""

    def __init__(self):
        self.screen = PROFILE_GRID
        self.contacts_ms = []

    def xpath(self, selector):
        return _Selection(self, _tree(self.screen).xpath(selector))

    def _touch(self, x, y, hold_ms):
        contact = hold_ms + _WORST_LAG_MS
        self.contacts_ms.append(contact)
        on_cell = any(
            left <= x < right and top <= y < bottom
            for left, top, right, bottom in (
                _bounds(node)
                for node in _tree(self.screen).xpath(
                    DETECTION_SELECTORS.post_thumbnail_selectors[0]
                )
            )
        )
        if self.screen is PROFILE_GRID and on_cell and contact < _PEEK_MS:
            self.screen = POST_VIEW
        # Past the threshold the peek preview opened and closed on release: still the grid.

    def long_click(self, x, y, duration):
        self._touch(x, y, duration * 1000.0)

    def click(self, x, y):
        self._touch(x, y, _U2_CLICK_HOLD_MS)


class _Scroll:
    @staticmethod
    def _plan_behavior_gesture(_context, _gesture):
        return {"distance_scale": 1.0, "velocity_scale": 1.0, "settle_scale": 1.0}


def _navigator(raw):
    nav = object.__new__(PostNavigationMixin)
    nav.device = DeviceFacade(raw)
    nav.logger = logger
    nav.detection_selectors = DETECTION_SELECTORS
    nav.post_selectors = POST_SELECTORS
    nav.scroll_actions = _Scroll()
    return nav


@pytest.fixture(autouse=True)
def _instant(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)


def test_the_fake_reproduces_the_device_failure():
    raw = _Instagram410Grid()
    left, top, right, bottom = raw.xpath(DETECTION_SELECTORS.post_thumbnail_selectors[0]).all()[0].bounds
    x, y = (left + right) // 2, (top + bottom) // 2
    # The Lab failure: 166 ms asked, 200 ms seen by Instagram, the post did not open.
    raw.long_click(x, y, 0.166)
    assert raw.screen is PROFILE_GRID
    raw.long_click(x, y, 0.100)
    assert raw.screen is POST_VIEW


def test_first_post_opens_on_every_tap():
    random.seed(410)
    failures = 0
    for _ in range(300):
        raw = _Instagram410Grid()
        if not _navigator(raw)._open_first_post_of_profile():
            failures += 1
    assert failures == 0, f"{failures} taps out of 300 turned into a peek instead of opening the post"


def test_reopening_an_unseen_cell_opens_on_every_tap():
    random.seed(4100)
    failures = 0
    for _ in range(300):
        raw = _Instagram410Grid()
        if not _navigator(raw)._open_entry_post_of_profile(0, reopening=True):
            failures += 1
    assert failures == 0, f"{failures} reopen taps out of 300 did not open the post"


def test_no_grid_tap_reaches_the_peek_threshold():
    random.seed(41)
    raw = _Instagram410Grid()
    nav = _navigator(raw)
    for _ in range(500):
        raw.screen = PROFILE_GRID
        nav._open_first_post_of_profile()
    assert max(raw.contacts_ms) < _PEEK_MS - 20.0
