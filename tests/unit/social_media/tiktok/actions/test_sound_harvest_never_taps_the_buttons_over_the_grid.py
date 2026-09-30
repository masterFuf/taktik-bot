"""The sound harvest opens a cell of the grid, never a button floated over the grid.

`SoundActions.collect_sound_users` opens the cells of a sound page one by one. Two buttons float over
the bottom of that page, drawn over its grid: on TikTok 43.1.4, « Ajouter à la Story » (`tbu`,
[28,1873][546,2044]) and « Utiliser le son » (`u8m`, [535,1874][1053,2044]) cover the third row of
cells ([0,1780]...[1080,2088]). The harvest clicked the centre of each cell, and the centre of the
seventh, (179, 1934), is inside « Ajouter à la Story »: that click opened the story editor (Lab,
Pixel 3a, 30/09, `max` = 10, the default of the sound scraping). On 47.0.3 the same two buttons
(« Publier en Story », « Utiliser le son ») cover the fourth row.

The screens are real dumps in French, anonymized (`scripts/lab/anonymize_dump.py`), read by
uiautomator2's own `XPathEntry` through the production action and the device facade:

- `tt4314_fr_sound_page_buttons_over_grid.xml`: TikTok 43.1.4, Pixel 3a, the page the harvest opened
  on 30/09, taken before `tt.sound.collect_users`;
- `tt4703_fr_sound_page_buttons_over_grid.xml`: TikTok 47.0.3, Pixel 6a (28/09), a page whose fourth
  row reaches under the buttons; their ids are not the reference's, the French labels find them;
- `tt4703_fr_sound_page_last_row_slivers.xml`: TikTok 47.0.3, Pixel 6a (29/09), a fourth row of which
  4 px show at the bottom of the page.

Every cell a button crosses is opened with every seed of the jitter played: no tap lands on a
button, and every tap lands in its cell. For every cell, the zone the tap is drawn in never meets a
button, which holds for any seed. A cell too little of which shows is not tapped at all, and no Back
follows: nothing was opened, and a Back would leave the page.
"""

import random

import pytest
import uiautomator2.xpath as u2_xpath
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.shared.behavior.tap as shared_tap
import taktik.core.shared.device.facade as shared_facade
import taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions as sound_module
import taktik.core.social_media.tiktok.services.profile.username as username_module
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions import SoundActions
from taktik.core.social_media.tiktok.actions.base.utils import first_matching
from taktik.core.social_media.tiktok.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import VIDEO_SOUND_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"


def _screen(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


#: 43.1.4, Pixel 3a (1080 x 2220): the grid and the two buttons that take the touch over it.
PAGE_4314 = _screen("tt4314_fr_sound_page_buttons_over_grid.xml")
GRID_4314 = [
    (0, 820, 358, 1297), (361, 820, 719, 1297), (722, 820, 1080, 1297),
    (0, 1300, 358, 1777), (361, 1300, 719, 1777), (722, 1300, 1080, 1777),
    (0, 1780, 358, 2088), (361, 1780, 719, 2088), (722, 1780, 1080, 2088),
]
BUTTONS_4314 = [(28, 1873, 546, 2044), (535, 1874, 1053, 2044)]

#: 47.0.3, Pixel 6a (1080 x 2400).
PAGE_4703 = _screen("tt4703_fr_sound_page_buttons_over_grid.xml")
GRID_4703 = [
    (0, 774, 358, 1251), (361, 774, 719, 1251), (722, 774, 1080, 1251),
    (0, 1254, 358, 1731), (361, 1254, 719, 1731), (722, 1254, 1080, 1731),
    (0, 1734, 358, 2211), (361, 1734, 719, 2211), (722, 1734, 1080, 2211),
    (0, 2214, 358, 2337), (361, 2214, 719, 2337), (722, 2214, 1080, 2337),
]
BUTTONS_4703 = [(26, 2132, 545, 2295), (535, 2133, 1054, 2295)]
SLIVERS_4703 = _screen("tt4703_fr_sound_page_last_row_slivers.xml")
SLIVERS = [(0, 2333, 358, 2337), (361, 2333, 719, 2337), (722, 2333, 1080, 2337)]

PAGES = {
    "43.1.4": (PAGE_4314, (1080, 2220), GRID_4314, BUTTONS_4314),
    "47.0.3": (PAGE_4703, (1080, 2400), GRID_4703, BUTTONS_4703),
}

#: The seeds of the tap jitter played for each cell a button crosses. The centre click of before
#: failed on every seed of those cells; a tap drawn over the whole cell, on most of them.
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


class _Phone:
    """Shows the capture, records every tap and every key; the xpath queries are uiautomator2's."""

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


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    clock = _Clock()
    for module in (u2_xpath, shared_base_action, shared_facade, sound_module, username_module):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    previous = active_locale()
    set_active_locale("fr")
    yield
    set_active_locale(previous)


@pytest.fixture
def tap_zones(monkeypatch):
    """The zone each humanized tap was drawn in, as the tap reports it."""
    zones = []

    def record(kind, **fields):
        if kind == "tap":
            zones.append(tuple(fields["bounds"]))

    monkeypatch.setattr(shared_tap, "emit_step", record)
    return zones


def _inside(point, bounds):
    """Android's hit test: the left and top edges belong to the element, the right and bottom do not."""
    x, y = point
    left, top, right, bottom = bounds
    return left <= x < right and top <= y < bottom


def _meet(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _found(screen, size, selectors):
    """Every element any of `selectors` finds, as a guarded tap reads them."""
    phone = _Phone(screen, size)
    bounds = []
    for selector in selectors:
        for element in phone.xpath(selector).all():
            if element.bounds not in bounds:
                bounds.append(element.bounds)
    return sorted(bounds)


@pytest.mark.parametrize("version", sorted(PAGES))
def test_the_captures_show_the_buttons_over_the_grid(version):
    screen, size, grid, buttons = PAGES[version]

    cells = first_matching(_Phone(screen, size), VIDEO_SOUND_SELECTORS.sound_video_cell)
    assert [cell.bounds for cell in cells] == grid
    assert _found(screen, size, VIDEO_SOUND_SELECTORS.buttons_over_grid) == buttons
    # A click at the centre of the last row lands on a button: what opened the story editor.
    last_row = grid[-3:]
    for cell in last_row:
        centre = ((cell[0] + cell[2]) // 2, (cell[1] + cell[3]) // 2)
        assert any(_inside(centre, button) for button in buttons), (cell, centre)


@pytest.mark.parametrize("version", sorted(PAGES))
def test_no_seed_of_the_jitter_taps_a_button_over_the_grid(version):
    screen, size, grid, buttons = PAGES[version]
    crossed = [(index, cell) for index, cell in enumerate(grid) if any(_meet(cell, b) for b in buttons)]
    assert len(crossed) == {"43.1.4": 3, "47.0.3": 6}[version]

    wrong = []
    for index, cell in crossed:
        for seed in SEEDS:
            phone = _Phone(screen, size)
            random.seed(seed)

            opened = SoundActions(phone)._open_cell(index)

            if not opened or len(phone.taps) != 1:
                wrong.append((index, seed, opened, phone.taps))
                continue
            tap = phone.taps[0]
            if not _inside(tap, cell) or any(_inside(tap, button) for button in buttons):
                wrong.append((index, seed, tap))

    assert wrong == [], f"{len(wrong)} of {len(crossed) * len(SEEDS)} cell taps wrong, first: {wrong[:3]}"


@pytest.mark.parametrize("version", sorted(PAGES))
def test_the_zone_a_cell_tap_is_drawn_in_never_meets_a_button(version, tap_zones):
    screen, size, grid, buttons = PAGES[version]

    for index, cell in enumerate(grid):
        tap_zones.clear()

        assert SoundActions(_Phone(screen, size))._open_cell(index) is True

        assert len(tap_zones) == 1, (index, tap_zones)
        [zone] = tap_zones
        assert cell[0] <= zone[0] < zone[2] <= cell[2] and cell[1] <= zone[1] < zone[3] <= cell[3], (index, zone)
        assert not any(_meet(zone, button) for button in buttons), (index, zone)


def test_the_reference_ids_find_the_buttons_whatever_the_language():
    set_active_locale("en")

    assert _found(PAGE_4314, (1080, 2220), VIDEO_SOUND_SELECTORS.buttons_over_grid) == BUTTONS_4314
    for index in (6, 7, 8):
        for seed in range(20):
            phone = _Phone(PAGE_4314, (1080, 2220))
            random.seed(seed)

            assert SoundActions(phone)._open_cell(index) is True
            [tap] = phone.taps
            assert not any(_inside(tap, button) for button in BUTTONS_4314), (index, seed, tap)


def test_a_cell_too_little_of_which_shows_is_left_alone():
    cells = first_matching(_Phone(SLIVERS_4703, (1080, 2400)), VIDEO_SOUND_SELECTORS.sound_video_cell)
    assert [cell.bounds for cell in cells][-3:] == SLIVERS

    for index in (9, 10, 11):
        phone = _Phone(SLIVERS_4703, (1080, 2400))

        assert SoundActions(phone)._handle_behind_cell(index) is None

        assert phone.taps == [], (index, phone.taps)
        assert phone.keys == [], (index, phone.keys)
