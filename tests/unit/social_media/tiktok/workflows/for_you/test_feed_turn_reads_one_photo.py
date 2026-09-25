"""A For You or search turn reads its screen on ONE photo, and reads again after a gesture.

The real workflow, detection and popup handler run on a phone whose screens are invented and read
by uiautomator2's own `XPathEntry`; only the gestures (swipe, close, watch) are stubbed. Before the
one-photo change, the top of a turn cost 37 dumps on a video.
"""

from types import SimpleNamespace

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.snapshot as snapshot_module
import taktik.core.social_media.tiktok.actions.business.workflows._internal.popup_handler as popup_module
import taktik.core.social_media.tiktok.actions.business.workflows.for_you.workflow as for_you_module
import taktik.core.social_media.tiktok.actions.business.workflows.search.workflow as search_module
import taktik.core.social_media.tiktok.actions.core.base_action as base_action_module
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.models import ForYouConfig
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.workflow import ForYouWorkflow
from taktik.core.social_media.tiktok.actions.business.workflows.search.models import SearchConfig
from taktik.core.social_media.tiktok.actions.business.workflows.search.workflow import SearchWorkflow
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale

PKG = "com.zhiliaoapp.musically:id/"


def _n(text="", desc="", rid="", selected="false"):
    rid = f"{PKG}{rid}" if rid else ""
    return (f'<node class="android.widget.TextView" text="{text}" content-desc="{desc}" resource-id="{rid}" '
            f'package="com.zhiliaoapp.musically" selected="{selected}" bounds="[0,0][10,10]" />')


def _video(author, *extra):
    return ('<hierarchy rotation="0">' + _n(desc="Pour toi") + _n(desc="Accueil", selected="true")
            + _n(text=author, rid="title") + _n(text="Une vidéo inventée", rid="desc")
            + _n(desc="Attribuer un « J'aime » à la vidéo. 12", rid="f57")
            + _n(desc="Partager une vidéo. 3 partages") + "".join(extra) + "</hierarchy>")


GDPR = _video("demo_author", _n(text="Nous avons mis à jour les transferts de données des utilisateurs "
                                     "de l'EEE vers la Chine"))


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    monotonic = perf_counter = time

    def sleep(self, seconds):
        self.now += max(float(seconds), 0.0)


class _Phone:
    wait_timeout = 1.0

    def __init__(self, clock, screen):
        self.clock, self.screen, self.dumps = clock, screen, 0
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        self.dumps += 1
        self.clock.now += 0.25
        return self.screen()


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
    for module in (snapshot_module, base_action_module, popup_module):
        monkeypatch.setattr(module, "time", fake)
    for module in (for_you_module, search_module):
        monkeypatch.setattr(module, "emit_step", lambda *_a, **_k: None)
    return fake


class _Feed:
    """The screens a run swipes through; `turns` records the dumps each turn took."""

    def __init__(self, clock, *screens):
        self.screens = list(screens)
        self.phone = _Phone(clock, lambda: self.screens[0])
        self.dumps_at_turn_start = []

    def next(self):
        if len(self.screens) > 1:
            self.screens.pop(0)
        return True


def _wire(wf, feed):
    wf._on_video_callback = None
    wf._on_stats_callback = None
    wf.scroll = SimpleNamespace(scroll_to_next_video=feed.next)
    wf._wait_if_paused = lambda: feed.dumps_at_turn_start.append(feed.phone.dumps) or True
    wf._check_pause_needed = lambda: None
    wf._behavior_reading_scale = lambda _key: 1.0
    return wf


def _for_you(feed, max_videos):
    wf = ForYouWorkflow(feed.phone, ForYouConfig(max_videos=max_videos, like_probability=0,
                                                 follow_probability=0, favorite_probability=0))
    wf._ensure_on_for_you = lambda: True

    def _watched(_info):
        wf.stats.videos_watched += 1

    wf._process_current_video = _watched
    return _wire(wf, feed)


def _turn_dumps(feed):
    marks = feed.dumps_at_turn_start + [feed.phone.dumps]
    return [after - before for before, after in zip(marks, marks[1:])]


def test_a_for_you_turn_costs_one_dump(clock):
    feed = _Feed(clock, _video("first_author"), _video("second_author"), _video("third_author"))
    wf = _for_you(feed, max_videos=3)
    wf.run()
    assert wf.stats.videos_watched == 3
    assert _turn_dumps(feed)[:3] == [1, 1, 1]


def test_a_popup_closed_is_a_gesture_the_turn_reads_again(clock):
    feed = _Feed(clock, GDPR, _video("second_author"))
    wf = _for_you(feed, max_videos=1)
    closed = []

    def _close_gdpr():
        closed.append("gdpr")
        feed.screens[0] = _video("demo_author")  # the popup is gone, the video is under it
        return True

    wf.click.close_gdpr_popup = _close_gdpr
    videos = []
    wf._on_video_callback = videos.append
    wf.run()
    assert closed == ["gdpr"] and wf.stats.popups_closed == 1
    assert _turn_dumps(feed)[0] == 2
    assert [info["author"] for info in videos] == ["demo_author"]


def test_a_search_turn_costs_one_dump(clock):
    feed = _Feed(clock, _video("first_author"), _video("second_author"))
    wf = SearchWorkflow(feed.phone, SearchConfig(search_query="demo", max_videos=2, like_probability=0,
                                                 follow_probability=0, favorite_probability=0))
    wf._navigate_to_search_videos = lambda: True
    wf._scroll_to_next = feed.next
    wf._watch_video = lambda _seconds: None
    wf._decide_and_execute_actions = lambda _info: None
    _wire(wf, feed).run()
    assert wf.stats.videos_watched == 2
    assert _turn_dumps(feed)[:2] == [1, 1]
