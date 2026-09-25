"""A TikTok cap of 0 is "never this action", and a stop during a video costs no extra swipe.

Two defects seen on the orphan runs of 2026-09-24:
- with maxLikesPerSession=0 the For You run ended in 5 s with 0 videos: `0 >= 0` read the cap
  as reached, and any reached cap ends the session. The followers workflow had the same test;
- the stop (the desktop gone, a block, the operator) was read at the top of the loop only, so
  the run finished its video and then swiped once more on a feed nobody was watching.
"""

from types import SimpleNamespace

import pytest

import taktik.core.social_media.tiktok.actions.business.workflows.for_you.workflow as for_you_module
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.tiktok.actions.business.workflows._internal import VideoWorkflowStats
from taktik.core.social_media.tiktok.actions.business.workflows.followers.workflow import (
    FollowersWorkflow,
)
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.models import ForYouConfig
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.workflow import ForYouWorkflow


@pytest.fixture(autouse=True)
def _clean_halt():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


class _Log:
    def __getattr__(self, _name):
        return lambda *_a, **_k: None


def _for_you(**config):
    wf = object.__new__(ForYouWorkflow)
    wf.config = ForYouConfig(**config)
    wf.stats = VideoWorkflowStats()
    wf.logger = _Log()
    return wf


@pytest.mark.parametrize("likes, follows", [(0, 20), (50, 0), (0, 0)])
def test_a_cap_of_zero_is_never_reached(likes, follows):
    wf = _for_you(max_likes_per_session=likes, max_follows_per_session=follows)

    assert wf._check_limits_reached() is False


def test_a_positive_cap_still_ends_the_session():
    wf = _for_you(max_likes_per_session=3, max_follows_per_session=0)
    wf.stats.videos_liked = 3

    assert wf._check_limits_reached() is True


def test_the_followers_workflow_reads_zero_the_same_way():
    wf = object.__new__(FollowersWorkflow)
    wf.config = SimpleNamespace(max_likes_per_session=0, max_follows_per_session=0)
    wf.stats = SimpleNamespace(likes=0, follows=0)

    assert wf._check_limits_reached() == ""


class _Scroll:
    def __init__(self):
        self.swipes = 0

    def scroll_to_next_video(self):
        self.swipes += 1
        return True


def _loop(monkeypatch, on_video):
    """A For You run without a phone: every video is the same, `on_video` runs as its turn."""
    monkeypatch.setattr(for_you_module, "emit_step", lambda *_a, **_k: None)
    wf = _for_you(max_videos=5, max_likes_per_session=0, max_follows_per_session=0,
                  skip_ads=False)
    wf._on_video_callback = None
    wf.scroll = _Scroll()
    wf.detection = SimpleNamespace(get_video_info=lambda **_: {"author": "a", "like_count": "1"})
    wf._ensure_on_for_you = lambda: True
    wf._wait_if_paused = lambda: True
    wf._handle_popups = lambda: False
    wf._handle_comments_section = lambda: False
    wf._handle_suggestion_page = lambda: False
    wf._handle_stuck_video = lambda _info: False
    wf._behavior_reading_scale = lambda _key: 1.0
    wf._train_on_video = lambda _info: False
    wf._check_pause_needed = lambda: None

    def _process(_info):
        wf.stats.videos_watched += 1
        on_video(wf)

    wf._process_current_video = _process
    return wf


def test_caps_of_zero_let_the_run_watch_its_videos(monkeypatch):
    wf = _loop(monkeypatch, on_video=lambda _wf: None)

    wf.run()

    assert wf.stats.videos_watched == 5


def test_a_stop_during_a_video_ends_the_run_without_one_more_swipe(monkeypatch):
    def _desktop_gone_on_the_second_video(wf):
        if wf.stats.videos_watched == 2:
            run_halt.demander_arret("desktop_gone")

    wf = _loop(monkeypatch, on_video=_desktop_gone_on_the_second_video)

    wf.run()

    # One swipe after the first video, none after the second.
    assert wf.stats.videos_watched == 2
    assert wf.scroll.swipes == 1
