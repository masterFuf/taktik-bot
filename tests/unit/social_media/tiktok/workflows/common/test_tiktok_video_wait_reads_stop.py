"""The wait on a TikTok video reads the run's stop latch, every half second.

Seen on a phone in TikTok 43.1.4: the latch was set (network lost, the desktop's watchdog), and
the workflow stopped 38 s later, at `_check_limits_reached` after the video, because the wait on
the current video was one `time.sleep` of its whole dwell. The For You feed, the hashtag search
and the profile videos of the followers road all waited that way.

The clock below is simulated: `time.sleep` adds to a counter instead of sleeping, and a stop is
asked once two seconds have gone by, as the watchdog's thread would. Without a stop, the dwell
slept is exactly the one drawn: the humanisation of the durations does not move.
"""

import time
import types

import pytest

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.tiktok.actions.atomic.scroll import scroll_actions
from taktik.core.social_media.tiktok.actions.atomic.scroll.scroll_actions import ScrollActions
from taktik.core.social_media.tiktok.workflows.automation.followers.interaction import (
    VideoInteractionMixin,
)
from taktik.core.social_media.tiktok.workflows.automation.search.workflow import SearchWorkflow
from taktik.core.social_media.tiktok.workflows.common.base_video_workflow import (
    BaseVideoWorkflow,
)
from taktik.core.social_media.tiktok.workflows.common.base_workflow import BaseTikTokWorkflow

_QUIET = type("L", (), {m: (lambda *a, **k: None)
                         for m in ("info", "debug", "warning", "success", "error")})()

DWELL = 30.0


class _Clock:
    """`time.sleep` without sleeping; asks for a stop once `stop_at` seconds have gone by."""

    def __init__(self, stop_at=None):
        self.slept = 0.0
        self.stop_at = stop_at

    def sleep(self, seconds):
        self.slept += seconds
        if self.stop_at is not None and self.slept >= self.stop_at:
            run_halt.demander_arret(run_halt.NETWORK_LOST, "test")


@pytest.fixture
def clock_with_stop(monkeypatch):
    clock = _Clock(stop_at=2.0)
    monkeypatch.setattr(time, "sleep", clock.sleep)
    return clock


@pytest.fixture
def clock_without_stop(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(time, "sleep", clock.sleep)
    return clock


def _scroll(monkeypatch):
    monkeypatch.setattr(scroll_actions, "sample_within", lambda *a, **k: DWELL)
    scroll = ScrollActions.__new__(ScrollActions)
    scroll.logger = _QUIET
    return scroll


def _search():
    search = SearchWorkflow.__new__(SearchWorkflow)
    search.logger = _QUIET
    return search


# --- For You: the action that watches the video ------------------------------------------------


def test_for_you_watch_ends_within_half_a_second_of_the_stop(monkeypatch, clock_with_stop):
    _scroll(monkeypatch).watch_video(DWELL)

    assert clock_with_stop.slept <= 2.5, f"watched {clock_with_stop.slept}s after a stop at 2s"


def test_for_you_watch_without_stop_keeps_the_dwell_drawn(monkeypatch, clock_without_stop):
    assert _scroll(monkeypatch).watch_video(DWELL) is True

    assert clock_without_stop.slept == pytest.approx(DWELL)


# --- hashtag search ---------------------------------------------------------------------------


def test_search_watch_ends_within_half_a_second_of_the_stop(clock_with_stop):
    _search()._watch_video(DWELL)

    assert clock_with_stop.slept <= 2.5


def test_search_watch_without_stop_keeps_the_dwell_planned(clock_without_stop):
    _search()._watch_video(DWELL)

    assert clock_without_stop.slept == pytest.approx(DWELL)


# --- after the wait: no gesture on a stopped run ----------------------------------------------


class _Clicks:
    def __init__(self):
        self.tapped = []

    def click_like_button(self):
        self.tapped.append("like")
        return True


class _Feed(BaseVideoWorkflow):
    def __init__(self):
        self.config = types.SimpleNamespace(
            like_probability=1.0, follow_probability=0.0, favorite_probability=0.0,
            max_likes_per_session=50, max_follows_per_session=50)
        self.stats = types.SimpleNamespace(videos_liked=0, users_followed=0, completion_reason="")
        self.click = _Clicks()
        self.detection = None
        self._actions_since_pause = 0
        self.logger = _QUIET


def test_a_stop_during_the_video_leaves_its_like_untried():
    feed = _Feed()
    run_halt.demander_arret(run_halt.NETWORK_LOST, "test")

    feed._decide_and_execute_actions({"author": "demo_creator", "is_liked": False})

    assert feed.click.tapped == [], "a like given after the run was asked to stop"


# --- followers road: the videos of a profile --------------------------------------------------


class _Walker(VideoInteractionMixin, BaseTikTokWorkflow):
    """One profile video, watched for its whole dwell unless the run is asked to stop."""

    def __init__(self):
        self.config = types.SimpleNamespace(
            min_watch_time=DWELL, max_watch_time=DWELL, like_probability=1.0,
            favorite_probability=0.0, comment_probability=0.0, max_likes_per_session=50,
            max_comments_per_session=0, min_posts_per_profile=1, max_posts_per_profile=1)
        self.stats = types.SimpleNamespace(likes=0, posts_watched=0, comments=0)
        self.detection = types.SimpleNamespace(get_video_info=lambda: {})
        self._current_profile_username = "demo_creator"
        self._running = True
        self._actions_since_pause = 0
        self.liked = []
        self.logger = _QUIET

    def _count_visible_posts(self):
        return 1

    def _posts_to_view(self, available_posts):
        return 1

    def _choose_grid_entry(self, available_posts):
        return 0

    def _click_profile_post(self, entry):
        return True

    def _remember_grid_entry(self, entry):
        pass

    def _human_delay(self):
        pass

    def _check_limits_reached(self):
        return False

    def _behavior_reading_scale(self, surface):
        return 1.0

    def _is_video_already_liked(self):
        return False

    def _try_like_video(self):
        self.liked.append("like")
        return True

    def _send_action(self, *args):
        pass

    def _send_stats_update(self):
        pass

    def _go_back(self):
        pass


def test_profile_video_wait_ends_within_half_a_second_of_the_stop(clock_with_stop):
    walker = _Walker()

    walker._interact_with_profile_posts()

    assert clock_with_stop.slept <= 2.5
    assert walker.liked == [], "a like given after the run was asked to stop"


def test_profile_video_wait_without_stop_keeps_the_dwell(clock_without_stop):
    walker = _Walker()
    walker.config.like_probability = 0.0

    walker._interact_with_profile_posts()

    # The dwell, then the half-second pause after going back to the profile.
    assert clock_without_stop.slept == pytest.approx(DWELL + 0.5)
