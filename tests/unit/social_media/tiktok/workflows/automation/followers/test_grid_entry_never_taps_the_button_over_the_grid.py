"""A profile visit enters the grid through a cell, never through the button floated over the grid.

`VideoInteractionMixin._click_profile_post` opens the cell of the profile's grid that the session
chose (runs of followers, target profiles, post links). On TikTok 46.6.3, once a video of the profile
has been watched, the profile floats « Vient d'être vue » over the bottom of its grid
(`user_just_watched_btn`, [639,2106][1038,2206] on a Pixel 6a), a button that scrolls the grid to
that video. The tap was drawn over the whole cell, so a tap on either of the last two cells of the
capture could land on that button.

The screen is a real dump of TikTok 46.6.3 in French (Pixel 6a, a visited profile, 01/09),
anonymized (`scripts/lab/anonymize_dump.py`), read by uiautomator2's own `XPathEntry` through the
production method, on the raw device the workflow holds, with the overrides of that version applied,
as at connection.
"""

import random
import types

import pytest
import uiautomator2.xpath as u2_xpath
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.shared.device.facade as shared_facade
from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.tiktok.actions.atomic.interaction.click_actions import ClickActions
from taktik.core.social_media.tiktok.actions.base.utils import first_matching
from taktik.core.social_media.tiktok.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from taktik.core.social_media.tiktok.workflows.automation.followers import interaction
from unit.paths import CORE

PROFILE = (CORE / "tests/unit/social_media/tiktok/fixtures/tt4663_fr_profile_just_watched_button.xml").read_text(
    encoding="utf-8"
)
SIZE = (1080, 2400)
#: The last row of the grid, whose last two cells « Vient d'être vue » crosses.
LAST_ROW = [(0, 1934, 358, 2337), (361, 1934, 719, 2337), (722, 1934, 1080, 2337)]
JUST_WATCHED = (639, 2106, 1038, 2206)
CROSSED = (7, 8)
SEEDS = range(100)


class _Clock:
    """Time moves only when the code waits."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    monotonic = perf_counter = time

    def sleep(self, seconds):
        self.now += max(0.0, seconds)


class _RawPhone:
    """The raw uiautomator2 device the workflow holds: the dump, and the taps it injects."""

    wait_timeout = 0.0

    def __init__(self):
        self.xpath = XPathEntry(self)
        self.taps = []

    def dump_hierarchy(self, *_a, **_k):
        return PROFILE

    def window_size(self):
        return SIZE

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration):
        self.taps.append((x, y))


class _Visit(interaction.VideoInteractionMixin):
    """A profile visit: the real `_click_profile_post`, with the click actions of the workflow."""

    def __init__(self, phone):
        self.device = phone
        self.followers_selectors = FOLLOWERS_SELECTORS
        self.logger = types.SimpleNamespace(debug=lambda *_: None, info=lambda *_: None)
        self.click = ClickActions(phone)


@pytest.fixture(autouse=True)
def _french_phone_on_46_6_3_no_waits(monkeypatch):
    clock = _Clock()
    for module in (u2_xpath, shared_base_action, shared_facade, interaction):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    previous = active_locale()
    set_active_locale("fr")
    apply_version_overrides("tiktok", "46.6.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")
    set_active_locale(previous)


def _inside(point, bounds):
    """Android's hit test: the left and top edges belong to the element, the right and bottom do not."""
    x, y = point
    left, top, right, bottom = bounds
    return left <= x < right and top <= y < bottom


def test_the_capture_shows_the_button_over_the_last_row():
    cells = first_matching(_RawPhone(), FOLLOWERS_SELECTORS.profile_post_item)

    assert [cell.bounds for cell in cells][-3:] == LAST_ROW
    for index in CROSSED:
        cell = cells[index].bounds
        assert cell[0] < JUST_WATCHED[2] and JUST_WATCHED[0] < cell[2] and cell[1] < JUST_WATCHED[3], cell


def test_no_seed_of_the_jitter_enters_the_grid_through_the_button():
    wrong = []
    for index in CROSSED:
        cell = LAST_ROW[index - 6]
        for seed in SEEDS:
            phone = _RawPhone()
            random.seed(seed)

            opened = _Visit(phone)._click_profile_post(index)

            if not opened or len(phone.taps) != 1:
                wrong.append((index, seed, opened, phone.taps))
                continue
            tap = phone.taps[0]
            if not _inside(tap, cell) or _inside(tap, JUST_WATCHED):
                wrong.append((index, seed, tap))

    assert wrong == [], f"{len(wrong)} of {len(CROSSED) * len(SEEDS)} grid entries wrong, first: {wrong[:3]}"
