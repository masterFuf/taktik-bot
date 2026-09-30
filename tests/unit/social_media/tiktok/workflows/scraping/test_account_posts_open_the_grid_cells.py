"""The scraping of an account's posts opens the cells of the grid, and nothing else on the page.

`ScrapingWorkflow._scrape_account_posts` opens the cells of a profile's grid one by one and comes
back to the grid after each. It clicked the centre of each element its cell list found, and two
screens made that click land outside the cell it meant:

- on TikTok 43.1.4 the list (`:id/e52`) also takes the container of the whole page for its first
  cell: the first click lands at the centre of the page ((540, 1154) on the capture, a chip of the
  profile's playlists), and every cell after it is one rank off;
- on TikTok 46.6.3, once a video of the profile has been watched, the profile floats « Vient d'être
  vue » over the bottom of the grid (`user_just_watched_btn`, [639,2106][1038,2206] on a Pixel 6a), a
  button that scrolls the grid: the centre of the last cell, (901, 2135), is inside it.

The screens are real dumps in French, anonymized (`scripts/lab/anonymize_dump.py`), read by
uiautomator2's own `XPathEntry` through the production loop, the overrides of each version applied as
at connection: `tt4314_fr_profile.xml` (43.1.4, Pixel 3a, a visited profile) and
`tt4663_fr_profile_just_watched_button.xml` (46.6.3, Pixel 6a, 01/09). The search that opens the
profile, the reading of the video once open and the scroll of the grid are not what is tested: the
profile is already on screen, nothing is collected, and a scroll is only counted. The budget is one cell
more than the grid shows, so the loop must open each cell once and then scroll, once: the cells it counts
are the cells it opens.
"""

import random

import pytest
import uiautomator2.xpath as u2_xpath
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.shared.device.facade as shared_facade
import taktik.core.social_media.tiktok.actions.atomic.interaction.post_link_actions as post_link_actions
import taktik.core.social_media.tiktok.actions.atomic.scroll.scroll_actions as scroll_actions
import taktik.core.social_media.tiktok.workflows.scraping.workflow as scraping_module
from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.tiktok.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.tiktok.workflows.scraping.models import ScrapingConfig
from taktik.core.social_media.tiktok.workflows.scraping.workflow import ScrapingWorkflow
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"

#: 43.1.4, Pixel 3a (1080 x 2220): the six cells of the grid.
PROFILE_4314 = (FIXTURES / "tt4314_fr_profile.xml").read_text(encoding="utf-8")
GRID_4314 = [
    (0, 1227, 358, 1704), (361, 1227, 719, 1704), (722, 1227, 1080, 1704),
    (0, 1707, 358, 2088), (361, 1707, 719, 2088), (722, 1707, 1080, 2088),
]
#: 46.6.3, Pixel 6a (1080 x 2400): the nine cells, and « Vient d'être vue » over the last row.
PROFILE_4663 = (FIXTURES / "tt4663_fr_profile_just_watched_button.xml").read_text(encoding="utf-8")
GRID_4663 = [
    (0, 974, 358, 1451), (361, 974, 719, 1451), (722, 974, 1080, 1451),
    (0, 1454, 358, 1931), (361, 1454, 719, 1931), (722, 1454, 1080, 1931),
    (0, 1934, 358, 2337), (361, 1934, 719, 2337), (722, 1934, 1080, 2337),
]
JUST_WATCHED = (639, 2106, 1038, 2206)

SCREENS = {
    "43.1.4": (PROFILE_4314, (1080, 2220), GRID_4314, []),
    "46.6.3": (PROFILE_4663, (1080, 2400), GRID_4663, [JUST_WATCHED]),
}
#: Runs of the whole loop, one seed of the tap jitter each.
SEEDS = range(30)


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
    """Shows the profile, records every tap and every key; the xpath queries are uiautomator2's."""

    wait_timeout = 0.0

    def __init__(self, screen, size):
        self.screen = screen
        self.size = size
        self.xpath = XPathEntry(self)
        self.taps = []
        self.keys = []

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def window_size(self):
        return self.size

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration):
        self.taps.append((x, y))

    def press(self, key):
        self.keys.append(key)


class _ProfileAlreadyOpen:
    """The search that opens the profile: the profile is the screen the phone shows."""

    def __init__(self, _device):
        pass

    def navigate_to_user_profile(self, _username):
        return True


@pytest.fixture
def scrolls(monkeypatch):
    """Each scroll of the profile's grid the loop asks for."""
    asked = []
    monkeypatch.setattr(scroll_actions.ScrollActions, "scroll_profile_videos",
                        lambda self, direction="down": asked.append(direction) or True)
    return asked


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    clock = _Clock()
    for module in (u2_xpath, shared_base_action, shared_facade, scraping_module):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    monkeypatch.setattr(scraping_module, "SearchActions", _ProfileAlreadyOpen)
    monkeypatch.setattr(post_link_actions.PostLinkActions, "collect_post", lambda self: None)
    monkeypatch.setattr(ScrapingWorkflow, "_local_db", lambda self: None)
    previous = active_locale()
    set_active_locale("fr")
    yield
    apply_version_overrides("tiktok", "43.1.4")
    set_active_locale(previous)


def _inside(point, bounds):
    """Android's hit test: the left and top edges belong to the element, the right and bottom do not."""
    x, y = point
    left, top, right, bottom = bounds
    return left <= x < right and top <= y < bottom


@pytest.mark.parametrize("version", sorted(SCREENS))
def test_each_cell_opened_is_the_cell_of_its_rank_and_clear_of_the_button(version, scrolls):
    screen, size, grid, floating = SCREENS[version]
    apply_version_overrides("tiktok", version)

    wrong = []
    for seed in SEEDS:
        phone = _Phone(screen, size)
        random.seed(seed)
        scrolls.clear()
        workflow = ScrapingWorkflow(phone, None, ScrapingConfig(scrape_type="account_posts",
                                                                max_posts_per_account=len(grid) + 1))

        workflow._scrape_account_posts("user_1")

        if scrolls != ["down"]:
            wrong.append((seed, "scrolls", list(scrolls)))

        if len(phone.taps) != len(grid):
            wrong.append((seed, "taps", phone.taps))
            continue
        for rank, (tap, cell) in enumerate(zip(phone.taps, grid)):
            if not _inside(tap, cell) or any(_inside(tap, box) for box in floating):
                wrong.append((seed, rank, tap, cell))
        if phone.keys != ["back"] * len(grid):
            wrong.append((seed, "keys", phone.keys))

    assert wrong == [], f"{len(wrong)} wrong in {len(SEEDS)} runs, first: {wrong[:3]}"
