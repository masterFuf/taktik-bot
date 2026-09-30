"""`_find_and_click(..., nth=i)` taps the element at rank `i` of the first selector that has one.

A grid is opened cell by cell: the cell at a rank, not the first element a selector finds. The screen
is a real capture of TikTok 43.1.4 in French (Pixel 3a, anonymized): the page of a sound, whose grid
shows nine cells, read by uiautomator2's own `XPathEntry` through the shared device facade.
"""

import random

import pytest
import uiautomator2.xpath as u2_xpath
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.shared.device.facade as shared_facade
from taktik.core.shared.actions.base_action import SharedBaseAction
from taktik.core.shared.diagnostics import miss_capture
from unit.paths import CORE

PAGE = (CORE / "tests/unit/social_media/tiktok/fixtures/tt4314_fr_sound_page_buttons_over_grid.xml").read_text(
    encoding="utf-8"
)
CELLS = ['//*[@resource-id="com.zhiliaoapp.musically:id/cover"][@clickable="true"]']
#: One element only: the « Ajouter à la Story » button of the page.
ONE = ['//*[@resource-id="com.zhiliaoapp.musically:id/tbu"]']
GRID = [
    (0, 820, 358, 1297), (361, 820, 719, 1297), (722, 820, 1080, 1297),
    (0, 1300, 358, 1777), (361, 1300, 719, 1777), (722, 1300, 1080, 1777),
    (0, 1780, 358, 2088), (361, 1780, 719, 2088), (722, 1780, 1080, 2088),
]


class _Clock:
    """Time moves only when the code waits."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    monotonic = perf_counter = time

    def sleep(self, seconds):
        self.now += max(0.0, seconds)


class _Phone:
    """Shows the capture, records every tap; the xpath queries are uiautomator2's."""

    wait_timeout = 0.0

    def __init__(self):
        self.xpath = XPathEntry(self)
        self.taps = []

    def dump_hierarchy(self, *_a, **_k):
        return PAGE

    def window_size(self):
        return 1080, 2220

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration):
        self.taps.append((x, y))


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    clock = _Clock()
    for module in (u2_xpath, shared_base_action, shared_facade):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)


def _inside(point, bounds):
    x, y = point
    left, top, right, bottom = bounds
    return left <= x < right and top <= y < bottom


@pytest.mark.parametrize("rank", range(len(GRID)))
def test_the_tap_lands_in_the_cell_of_that_rank(rank):
    for seed in range(10):
        phone = _Phone()
        random.seed(seed)

        assert SharedBaseAction(phone)._find_and_click(CELLS, nth=rank, timeout=1) is True

        [tap] = phone.taps
        assert _inside(tap, GRID[rank]), (rank, seed, tap)


def test_a_selector_without_that_rank_gives_way_to_the_next():
    phone = _Phone()

    assert SharedBaseAction(phone)._find_and_click(ONE + CELLS, nth=3, timeout=1) is True

    [tap] = phone.taps
    assert _inside(tap, GRID[3]), tap


def test_no_element_at_that_rank_taps_nothing():
    phone = _Phone()

    assert SharedBaseAction(phone)._find_and_click(CELLS, nth=len(GRID), timeout=1) is False

    assert phone.taps == []
