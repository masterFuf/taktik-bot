"""A For You or search turn that reads a creator's profile counts nothing and returns to its feed.

Diagnostic reported by PR #16: a long For You session ended on a creator's profile and went on
"watching" its grid, one video counted per swipe. The screens are real TikTok 43.1.4 captures in
French (Pixel 3a), anonymized, read by uiautomator2's own `XPathEntry`: a For You video
(`tt4314_fr_for_you_video.xml`), a creator's profile (`tt4314_fr_profile.xml`) and a second video,
without a description (`tt4314_fr_for_you_video_no_description.xml`). The real workflow, detection,
popup handler and return to For You run on them; only the gestures (swipe, Home, For You tab, Back,
watch) are stubbed.
"""

from types import SimpleNamespace

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.snapshot as snapshot_module
import taktik.core.social_media.tiktok.workflows.common.popup_handler as popup_module
import taktik.core.social_media.tiktok.workflows.automation.for_you.workflow as for_you_module
import taktik.core.social_media.tiktok.workflows.automation.search.workflow as search_module
import taktik.core.social_media.tiktok.actions.base.base_action as base_action_module
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.tiktok.workflows.automation.for_you.models import ForYouConfig
from taktik.core.social_media.tiktok.workflows.automation.for_you.workflow import ForYouWorkflow
from taktik.core.social_media.tiktok.workflows.automation.search.models import SearchConfig
from taktik.core.social_media.tiktok.workflows.automation.search.workflow import SearchWorkflow
from taktik.core.social_media.tiktok.workflows.common.feed_interruptions import MAX_FAILED_RETURNS_TO_FEED
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
VIDEO = (FIXTURES / "tt4314_fr_for_you_video.xml").read_text(encoding="utf-8")
PROFILE = (FIXTURES / "tt4314_fr_profile.xml").read_text(encoding="utf-8")
SECOND = (FIXTURES / "tt4314_fr_for_you_video_no_description.xml").read_text(encoding="utf-8")


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    monotonic = perf_counter = time

    def sleep(self, seconds):
        self.now += max(float(seconds), 0.0)


class _Phone:
    """Shows the first screen of the list; a gesture stub moves to the next one."""

    wait_timeout = 1.0

    def __init__(self, clock, screens):
        self.clock, self.screens = clock, list(screens)
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        self.clock.now += 0.25
        return self.screens[0]

    def next_screen(self):
        if len(self.screens) > 1:
            self.screens.pop(0)
        return True

    def window_size(self):
        return 1080, 2220


@pytest.fixture(autouse=True)
def _french_and_no_halt():
    set_active_locale("fr")
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()
    set_active_locale(None)


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    for module in (snapshot_module, base_action_module, popup_module, for_you_module, search_module):
        monkeypatch.setattr(module, "time", fake)
    for module in (for_you_module, search_module):
        monkeypatch.setattr(module, "emit_step", lambda *_a, **_k: None)
    return fake


def _common_wiring(wf, phone, cards):
    wf._on_video_callback = cards.append
    wf._on_stats_callback = None
    wf._wait_if_paused = lambda: True
    wf._check_pause_needed = lambda: None
    wf._behavior_reading_scale = lambda _key: 1.0
    return wf


def _for_you(phone, max_videos, cards, home_reached=True):
    """The real For You loop and its real return to For You; Home and the tab are stubbed."""
    wf = ForYouWorkflow(phone, ForYouConfig(max_videos=max_videos, like_probability=0,
                                            follow_probability=0, favorite_probability=0))
    wf.scroll = SimpleNamespace(scroll_to_next_video=phone.next_screen)
    homes = []

    def _home():
        homes.append(phone.screens[0] is PROFILE)
        return phone.next_screen() if home_reached else False

    wf.navigation.navigate_to_home = _home
    wf.click.click_for_you_tab = lambda: True

    def _watched(info):
        wf.stats.videos_watched += 1

    wf._process_current_video = _watched
    return _common_wiring(wf, phone, cards), homes


def _authors(cards):
    return [card.get("author") for card in cards]


def test_the_captures_are_what_the_test_says(clock):
    """The reader names each capture: two videos with an author, and a profile."""
    phone = _Phone(clock, [VIDEO])
    wf, _ = _for_you(phone, 1, [])
    for xml, kind in ((VIDEO, "video"), (PROFILE, "profile"), (SECOND, "video")):
        phone.screens = [xml]
        assert wf.detection.read_screen().kind == kind
    phone.screens = [VIDEO]
    assert wf.detection.get_video_info(screen=wf.detection.read_screen())["author"]


def test_a_profile_in_the_for_you_feed_is_left_without_counting_a_video(clock):
    phone = _Phone(clock, [VIDEO, PROFILE, SECOND])
    cards = []
    wf, homes = _for_you(phone, max_videos=2, cards=cards)
    wf.run()

    assert wf.stats.videos_watched == 2
    # Two video cards, each with its author: none for the profile.
    assert len(cards) == 2 and all(_authors(cards))
    # Home was reached once, from the profile, and the run then watched the SECOND video.
    assert homes == [True]
    assert phone.screens == [SECOND]
    assert wf.stats.errors == 0 and not wf.stats.completion_reason


def test_a_feed_that_cannot_be_reached_again_stops_the_run(clock):
    phone = _Phone(clock, [VIDEO, PROFILE])
    cards = []
    wf, homes = _for_you(phone, max_videos=10, cards=cards, home_reached=False)
    wf.run()

    assert wf.stats.videos_watched == 1 and len(cards) == 1
    assert len(homes) == MAX_FAILED_RETURNS_TO_FEED
    assert wf.stats.errors == MAX_FAILED_RETURNS_TO_FEED
    assert wf.stats.completion_reason == "navigation_failed"


def test_a_profile_in_the_search_feed_is_left_by_back(clock):
    phone = _Phone(clock, [VIDEO, PROFILE, SECOND])
    cards = []
    wf = SearchWorkflow(phone, SearchConfig(search_query="demo", max_videos=2, like_probability=0,
                                            follow_probability=0, favorite_probability=0))
    wf._navigate_to_search_videos = lambda: True
    wf._scroll_to_next = phone.next_screen
    wf._watch_video = lambda _seconds: None
    wf._decide_and_execute_actions = lambda _info: None
    backs = []

    def _back():
        backs.append(phone.screens[0] is PROFILE)
        return phone.next_screen()

    wf.navigation.go_back = _back
    _common_wiring(wf, phone, cards).run()

    assert wf.stats.videos_watched == 2
    assert len(cards) == 2 and all(_authors(cards))
    assert backs == [True]
    assert wf.stats.errors == 0
