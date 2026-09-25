"""Each feed turn emits what reading its screen cost (M1), by what the screen turned out to be.

The For You and search loops read the screen at the top of every turn: popups, comment sheet,
suggestion page, then the video. One `device_io` step `tiktok.feed.decision` per turn gives the
before and after of the one-photo change, per kind of screen. Videos are invented.
"""

from types import SimpleNamespace

import pytest

import taktik.core.social_media.tiktok.actions.business.workflows.for_you.workflow as for_you_module
import taktik.core.social_media.tiktok.actions.business.workflows.search.workflow as search_module
from taktik.core.shared.diagnostics import run_halt
from taktik.core.shared.telemetry import clear_telemetry_sink, configure_telemetry_sink
from taktik.core.social_media.tiktok.actions.business.workflows._internal import (
    BaseVideoWorkflow,
    VideoWorkflowStats,
)
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.models import ForYouConfig
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.workflow import ForYouWorkflow
from taktik.core.social_media.tiktok.actions.business.workflows.search.models import SearchConfig
from taktik.core.social_media.tiktok.actions.business.workflows.search.workflow import SearchWorkflow

VIDEO = {"author": "demo_author", "like_count": "12"}
AD = {"author": "demo_brand", "is_ad": True}
LIVE = {"author": None, "is_live": True}


@pytest.fixture(autouse=True)
def _clean_halt():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


@pytest.fixture
def decisions():
    received = []
    configure_telemetry_sink(received.append)
    yield lambda: [(s.detail.get("source"), s.detail.get("kind"))
                   for s in received if s.category == "device_io" and s.action == "tiktok.feed.decision"]
    clear_telemetry_sink()


class _Log:
    def __getattr__(self, _name):
        return lambda *_a, **_k: None


def _screens(*infos):
    queue = list(infos)
    return lambda **_: dict(queue.pop(0) if len(queue) > 1 else queue[0])


def _wire(wf, video_infos, monkeypatch, module):
    monkeypatch.setattr(module, "emit_step", lambda *_a, **_k: None)
    wf.stats = VideoWorkflowStats()
    wf.logger = _Log()
    wf._on_video_callback = None
    wf._on_stats_callback = None
    wf.scroll = SimpleNamespace(scroll_to_next_video=lambda: True)
    wf.detection = SimpleNamespace(read_screen=lambda **_: "photo", get_video_info=_screens(*video_infos))
    wf._wait_if_paused = lambda: True
    wf._handle_popups = lambda _screen=None: False
    wf._handle_stuck_video = lambda _info: False
    wf._behavior_reading_scale = lambda _key: 1.0
    wf._check_pause_needed = lambda: None
    return wf


def _for_you(monkeypatch, video_infos, *, sheets=()):
    wf = object.__new__(ForYouWorkflow)
    wf.config = ForYouConfig(max_videos=len(video_infos), max_likes_per_session=0,
                             max_follows_per_session=0, skip_ads=True)
    _wire(wf, video_infos, monkeypatch, for_you_module)
    sheet_queue = list(sheets)
    wf._ensure_on_for_you = lambda: True
    wf._handle_comments_section = lambda _screen: bool(sheet_queue) and sheet_queue.pop(0) == "comments"
    wf._handle_suggestion_page = lambda _screen: False
    wf._train_on_video = lambda _info: False

    def _process(_info):
        wf.stats.videos_watched += 1

    wf._process_current_video = _process
    return wf


def test_every_for_you_turn_emits_its_cost_by_kind_of_screen(monkeypatch, decisions):
    wf = _for_you(monkeypatch, [VIDEO, AD, LIVE, VIDEO, VIDEO])
    wf.run()
    assert decisions()[:5] == [("for_you", "video"), ("for_you", "ad"), ("for_you", "live"),
                               ("for_you", "video"), ("for_you", "video")]


def test_a_turn_that_closes_a_comment_sheet_is_counted_as_one(monkeypatch, decisions):
    wf = _for_you(monkeypatch, [VIDEO, VIDEO], sheets=["comments"])
    wf.run()
    assert decisions()[:2] == [("for_you", "comments"), ("for_you", "video")]


def test_every_search_turn_emits_its_cost_by_kind_of_screen(monkeypatch, decisions):
    wf = object.__new__(SearchWorkflow)
    wf.config = SearchConfig(search_query="demo", max_videos=2, max_likes_per_session=0,
                             max_follows_per_session=0, skip_ads=True)
    _wire(wf, [AD, VIDEO], monkeypatch, search_module)
    wf._navigate_to_search_videos = lambda: True
    wf._scroll_to_next = lambda: None
    wf._should_skip_video = lambda _info: False
    wf._decide_and_execute_actions = lambda _info: None

    def _watch(_seconds):
        return None

    wf._watch_video = _watch
    wf.run()
    assert decisions()[:2] == [("search", "ad"), ("search", "video")]


@pytest.mark.parametrize("info, kind", [
    (VIDEO, "video"), (AD, "ad"), (LIVE, "live"), ({"author": None}, "unknown"),
    ({"author": "demo_brand", "is_ad": True, "is_live": True}, "live"),
])
def test_the_kind_comes_from_the_video_info(info, kind):
    assert BaseVideoWorkflow._screen_kind(info) == kind
