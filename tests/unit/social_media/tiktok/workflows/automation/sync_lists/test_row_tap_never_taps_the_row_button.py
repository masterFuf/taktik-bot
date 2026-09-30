"""Opening a row of our own follow lists never taps the row's own button.

`SyncListsWorkflow._tap_row_by_display_name` opens the profile behind a row the list did not name
(`resolveMissingHandles`). The row it taps is the whole clickable line, and that line holds the
relationship button on its right: « Suivis » / « Amis » on the Following list (a tap there unfollows,
TikTok asks nothing), « Suivre » on the Followers list (a tap there follows back). A humanized tap
sampled over the whole row landed on that button several times in a hundred.

The screens are real dumps of TikTok 47.0.3 in French (the operated account's own lists), anonymized,
read by uiautomator2's own `XPathEntry` through the production workflow method and the click actions.
Every seed of the tap jitter is played; the tap must land in the row, and never on a row button.
"""

import random

import pytest
import uiautomator2.xpath as u2_xpath
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.shared.device.facade as shared_facade
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.tiktok.actions.atomic.interaction.click_actions import ClickActions
from taktik.core.social_media.tiktok.actions.base.utils import first_matching
from taktik.core.social_media.tiktok.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from taktik.core.social_media.tiktok.workflows.automation.sync_lists import SyncListsWorkflow
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
#: (capture, the display name of the row opened): the second row of each list.
LISTS = [
    ("tt4703_fr_following_list.xml", "name_8"),
    ("tt4703_fr_followers_list.xml", "name_8"),
]
#: The seeds of the tap jitter played on each list.
SEEDS = range(200)


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

    def __init__(self, screen):
        self.screen = screen
        self.xpath = XPathEntry(self)
        self.taps = []

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def window_size(self):
        return 1080, 2220

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration):
        self.taps.append((x, y))


class _SilentLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    clock = _Clock()
    for module in (u2_xpath, shared_base_action, shared_facade):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    previous = active_locale()
    set_active_locale("fr")
    yield
    set_active_locale(previous)


def _workflow(phone) -> SyncListsWorkflow:
    workflow = SyncListsWorkflow.__new__(SyncListsWorkflow)
    workflow.logger = _SilentLogger()
    workflow.device = phone
    workflow.selectors = FOLLOWERS_SELECTORS
    workflow.click = ClickActions(phone)
    return workflow


def _inside(point, bounds):
    """Android's hit test: the left and top edges belong to the element, the right and bottom do not."""
    x, y = point
    left, top, right, bottom = bounds
    return left <= x < right and top <= y < bottom


@pytest.mark.parametrize("capture, name", LISTS)
def test_the_row_holds_its_button(capture, name):
    screen = (FIXTURES / capture).read_text(encoding="utf-8")
    [row] = first_matching(_Phone(screen), FOLLOWERS_SELECTORS.row_selectors_for_display_name(name))
    buttons = [button.bounds for button in first_matching(_Phone(screen), FOLLOWERS_SELECTORS.follower_any_button)]

    inside_the_row = [
        button for button in buttons
        if row.bounds[0] <= button[0] and button[2] <= row.bounds[2]
        and row.bounds[1] <= button[1] and button[3] <= row.bounds[3]
    ]
    assert len(inside_the_row) == 1, (row.bounds, buttons)


@pytest.mark.parametrize("capture, name", LISTS)
def test_no_seed_of_the_jitter_taps_a_row_button(capture, name):
    screen = (FIXTURES / capture).read_text(encoding="utf-8")
    [row] = first_matching(_Phone(screen), FOLLOWERS_SELECTORS.row_selectors_for_display_name(name))
    buttons = [button.bounds for button in first_matching(_Phone(screen), FOLLOWERS_SELECTORS.follower_any_button)]

    on_a_button = []
    for seed in SEEDS:
        phone = _Phone(screen)
        random.seed(seed)

        assert _workflow(phone)._tap_row_by_display_name(name) is True

        assert len(phone.taps) == 1, (seed, phone.taps)
        tap = phone.taps[0]
        assert _inside(tap, row.bounds), (seed, tap)
        if any(_inside(tap, button) for button in buttons):
            on_a_button.append((seed, tap))

    assert on_a_button == []
