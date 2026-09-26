"""The videos watched on a TikTok profile are drawn in a range, not a fixed count.

Every profile of every run used to get exactly `posts_per_profile` videos (2 by default): the same
number on every visit, a regularity no person shows. The page now sends a range
(`minPostsPerProfile`, `maxPostsPerProfile`); each profile draws its count with the per-profile
count law of the like target (`interaction_plan.sample_like_target`), leaning with the session's
appetite, on its own stream (`BehaviorSessionState.posts_to_view`). Strict regression runs keep the
upper bound, the former fixed count.
"""

import statistics
import types

import pytest

from taktik.core.shared.behavior.session_state import BehaviorSessionState
from taktik.core.social_media.tiktok.actions.business.workflows.followers import interaction
from taktik.core.social_media.tiktok.actions.business.workflows.followers.models import FollowersConfig
from taktik.core.social_media.tiktok.actions.business.workflows.followers.payload import (
    followers_settings_from_payload,
)

PAGE = {"minPostsPerProfile": 1, "maxPostsPerProfile": 4}


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    monkeypatch.setattr(interaction.time, "sleep", lambda *_: None)
    monkeypatch.setattr(interaction, "video_watch_seconds", lambda *_a, **_k: 0.0)


class Visit(interaction.VideoInteractionMixin):
    """One profile visit: the real `_interact_with_profile_posts`, the phone left out."""

    def __init__(self, config, state, visible=9):
        self.config = config
        self.behavior_state = state
        self.stats = types.SimpleNamespace(posts_watched=0)
        self.logger = types.SimpleNamespace(debug=lambda *_: None, info=lambda *_: None)
        self.detection = types.SimpleNamespace(get_video_info=lambda: {})
        self._running = True
        self._actions_since_pause = 0
        self._current_profile_username = "someone"
        self._visible = visible

    def _count_visible_posts(self):
        return self._visible

    def _click_profile_post(self, index):
        return True

    def _human_delay(self):
        pass

    def _check_limits_reached(self):
        return False

    def _behavior_reading_scale(self, _context):
        return 1.0

    def _interact_with_current_video(self):
        pass

    def _swipe_to_next_video(self):
        pass

    def _send_stats_update(self):
        pass

    def _send_action(self, *_a, **_k):
        pass

    def _go_back(self):
        pass


def _config(payload):
    return FollowersConfig(**followers_settings_from_payload(payload))


def _watched(config, state, visible=9):
    visit = Visit(config, state, visible)
    visit._interact_with_profile_posts()
    return visit.stats.posts_watched


def test_the_page_range_reaches_the_config():
    config = _config(PAGE)

    assert (config.min_posts_per_profile, config.max_posts_per_profile) == (1, 4)


def test_each_profile_draws_its_count_in_the_range():
    config = _config(PAGE)
    counts = [_watched(config, BehaviorSessionState(seed=seed)) for seed in range(600)]

    assert set(counts) == {1, 2, 3, 4}, sorted(set(counts))
    # The law of the like target over an unknown size: uniform on the range, mean at its middle.
    assert abs(statistics.mean(counts) - 2.5) < 0.2


def test_one_session_does_not_watch_the_same_count_everywhere():
    config = _config(PAGE)
    state = BehaviorSessionState(seed=7)

    counts = [_watched(config, state) for _ in range(40)]

    assert len(set(counts)) > 1


def test_the_grid_caps_the_draw_without_piling_on_it():
    config = _config({"minPostsPerProfile": 1, "maxPostsPerProfile": 6})
    counts = [_watched(config, BehaviorSessionState(seed=seed), visible=2) for seed in range(400)]

    assert set(counts) == {1, 2}
    assert 0.35 < counts.count(2) / len(counts) < 0.65


def test_a_read_only_run_watches_nothing():
    """The qualification dialog sends 0: read the profile, touch nothing."""
    config = _config({"minPostsPerProfile": 0, "maxPostsPerProfile": 0})

    assert _watched(config, BehaviorSessionState(seed=1)) == 0


def test_the_single_value_of_older_payloads_is_the_upper_bound():
    """A saved node, the CLI or an Agent plan may still send `postsPerProfile` alone."""
    config = _config({"postsPerProfile": 3})

    assert (config.min_posts_per_profile, config.max_posts_per_profile) == (1, 3)
    assert _config({"postsPerProfile": 0}).max_posts_per_profile == 0


def test_strict_regression_keeps_the_former_fixed_count():
    config = _config(PAGE)
    state = BehaviorSessionState(seed=3, strict_regression=True)

    assert {_watched(config, state) for _ in range(30)} == {4}


def test_the_draw_does_not_shift_a_seeded_gesture_decision():
    """Same seed, a drawn range or a fixed one: the grid cells opened are the same."""
    drawn, fixed = BehaviorSessionState(seed=5), BehaviorSessionState(seed=5)

    for _ in range(10):
        _watched(_config(PAGE), drawn)
        _watched(_config({"minPostsPerProfile": 4, "maxPostsPerProfile": 4}), fixed)

    assert [e["index"] for e in drawn.grid_entry_history] == [e["index"] for e in fixed.grid_entry_history]
