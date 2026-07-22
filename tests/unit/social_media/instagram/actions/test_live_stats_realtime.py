"""Live counters must move at the GESTURE, not at the end of the profile.

Operator report: with 3 likes planned on a profile, the desktop live panel sat at 0 for
the whole profile (30-90s of taps, scrolls and human delays) then jumped straight to 3.
`BaseStatsManager.increment` publishes a stats snapshot on every call, so the panel is only
as live as the increments are granular — and the callers used to add the profile's TOTALS
once it was done (`increment('likes', 3)`).

These tests lock the fixed contract:
  - each landed like/comment reaches the stats manager as its own +1, in order;
  - the follow and every story slide count at the moment of the gesture;
  - the callers no longer re-add the totals (that would double every counter).
"""

import types

import taktik.core.social_media.instagram.actions.core.base_business.interaction_engine as ie
from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (
    InteractionEngineMixin,
)
from taktik.core.social_media.instagram.actions.core.base_business.config_parsing import (
    ConfigParsingMixin,
)


class _Logger:
    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
    def error(self, *a, **k): pass


class _Stats:
    """Records the increment SEQUENCE — the panel sees exactly this, in this order."""

    def __init__(self):
        self.increments = []

    def increment(self, key, value=1):
        self.increments.append((key, value))

    def running_total(self, key):
        return sum(v for k, v in self.increments if k == key)


class _LikeBusiness:
    """Stands in for LikeOrchestration: fires the injected callbacks per landed gesture."""

    def __init__(self, posts_liked=0, posts_commented=0):
        self.posts_liked = posts_liked
        self.posts_commented = posts_commented
        self.received_on_like = None
        self.received_on_comment = None

    def like_profile_posts(self, *a, on_like=None, on_comment=None, **k):
        self.received_on_like = on_like
        self.received_on_comment = on_comment
        for _ in range(self.posts_liked):
            if on_like:
                on_like()
        for _ in range(self.posts_commented):
            if on_comment:
                on_comment()
        return {'posts_liked': self.posts_liked, 'posts_commented': self.posts_commented}


class _ClickActions:
    def __init__(self, follow_ok=True):
        self.follow_ok = follow_ok
        self.follow_calls = 0

    def follow_user(self, username):
        self.follow_calls += 1
        return self.follow_ok


class _ScrollActions:
    def scroll_to_top(self, *a, **k):
        return True


class _DetectionActions:
    def __init__(self, has_story=False):
        self.has_story = has_story

    def has_unseen_profile_story(self, *a, **k):
        return self.has_story


class _Engine(InteractionEngineMixin, ConfigParsingMixin):
    def __init__(self, like_business, click_actions, story_result=None):
        self.logger = _Logger()
        self.stats_manager = _Stats()
        self.like_business = like_business
        self.click_actions = click_actions
        self.scroll_actions = _ScrollActions()
        self.detection_actions = _DetectionActions(has_story=story_result is not None)
        self._story_result = story_result

    def _emit_like_event(self, *a, **k): pass
    def _emit_follow_event(self, *a, **k): pass
    def _emit_story_event(self, *a, **k): pass
    def _record_action(self, *a, **k): pass
    def _handle_follow_suggestions_popup(self): pass
    def _recover_from_blocking_modal(self, *a, **k): return None
    def _action_timestamp(self, *a, **k): return '2026-01-01 00:00:00'

    def _view_stories_on_current_profile(self, *a, **k):
        return self._story_result


def _cfg(**overrides):
    base = {
        'like_probability': 1.0,
        'follow_probability': 0.0,
        'comment_probability': 0.0,
        'story_probability': 0.0,
        'story_like_probability': 0.0,
        'min_likes_per_profile': 1,
    }
    base.update(overrides)
    return base


def test_each_like_counts_on_its_own_gesture():
    eng = _Engine(_LikeBusiness(posts_liked=3), _ClickActions(follow_ok=False))

    eng._perform_interactions_on_profile('alice', _cfg(), profile_data=None)

    # Three separate +1 — the panel ticks 1, 2, 3 — never a single +3 at the end.
    assert eng.stats_manager.increments == [('likes', 1), ('likes', 1), ('likes', 1)]
    assert eng.stats_manager.running_total('likes') == 3


def test_engine_injects_callbacks_into_the_like_layer():
    like_biz = _LikeBusiness(posts_liked=1)
    eng = _Engine(like_biz, _ClickActions(follow_ok=False))

    eng._perform_interactions_on_profile('bob', _cfg(), profile_data=None)

    # LikeOrchestration owns a DIFFERENT stats manager, so it can only report back
    # through these callbacks; losing them silently freezes the panel again.
    assert callable(like_biz.received_on_like)
    assert callable(like_biz.received_on_comment)


def test_comments_are_counted_at_all():
    # Regression: target/hashtag never incremented 'comments', so the live panel's
    # Commentaires card stayed at 0 no matter how many comments were posted.
    like_biz = _LikeBusiness(posts_liked=1, posts_commented=2)
    eng = _Engine(like_biz, _ClickActions(follow_ok=False))

    eng._perform_interactions_on_profile('carol', _cfg(comment_probability=1.0), profile_data=None)

    assert eng.stats_manager.running_total('comments') == 2


def test_follow_counts_at_the_gesture():
    eng = _Engine(_LikeBusiness(posts_liked=0), _ClickActions(follow_ok=True))

    eng._perform_interactions_on_profile('dave', _cfg(follow_probability=1.0), profile_data=None)

    assert ('follows', 1) in eng.stats_manager.increments


def test_failed_follow_counts_nothing():
    eng = _Engine(_LikeBusiness(posts_liked=0), _ClickActions(follow_ok=False))

    eng._perform_interactions_on_profile('erin', _cfg(follow_probability=1.0), profile_data=None)

    assert eng.stats_manager.running_total('follows') == 0


def test_every_story_slide_counts_as_it_is_watched(monkeypatch):
    """Drives the REAL story loop: one +1 per watched slide and per liked slide.

    The callers used to add a flat +1 for the whole profile regardless of how many
    slides were watched, so a 3-slide story showed as 1.
    """
    monkeypatch.setattr(ie.time, "sleep", lambda _s: None)
    monkeypatch.setattr(ie.random, "uniform", lambda a, b: a)
    monkeypatch.setattr(ie, "sample_story_like_count", lambda *a, **k: 2)
    monkeypatch.setattr(ie, "sample_story_like_slots", lambda *a, **k: [0, 2])

    class _Detection:
        def __init__(self, slides):
            self._slides = slides
            self._open_calls = 0

        def has_stories(self):
            return True

        def is_story_viewer_open(self):
            self._open_calls += 1
            return self._open_calls <= self._slides

        def get_story_count_from_viewer(self):
            return (1, self._slides)

        def get_story_viewer_metadata(self):
            return {}

    class _Clicks:
        def click_story_ring(self): return True
        def like_story(self): return True
        def close_story(self): return True

    class _Nav:
        def __init__(self, slides): self._left = slides
        def navigate_to_next_story(self):
            self._left -= 1
            return self._left > 0

    class _Host(InteractionEngineMixin):
        def __init__(self, slides):
            self.logger = _Logger()
            self.stats_manager = _Stats()
            self.detection_actions = _Detection(slides)
            self.click_actions = _Clicks()
            self.nav_actions = _Nav(slides)
            self.device = types.SimpleNamespace(press=lambda *_a, **_k: None)

        def _human_like_delay(self, *a, **k): return None
        def _record_action(self, *a, **k): return None
        def _action_timestamp(self, *a, **k): return '2026-01-01 00:00:00'
        def _recover_from_blocking_modal(self, *a, **k): return None

    host = _Host(3)
    res = host._view_stories_on_current_profile(
        'frank', do_story_like=True, max_story_likes=3, fallback_like_slot=-1, max_stories=3,
    )

    assert res['stories_viewed'] == 3
    assert host.stats_manager.running_total('stories_watched') == 3
    assert host.stats_manager.running_total('story_likes') == res['stories_liked']
    # 'story_likes' is the declared counter; 'stories_liked' silently logged
    # "Unknown statistic" and lost every story like.
    assert host.stats_manager.running_total('stories_liked') == 0


def test_like_orchestration_never_publishes_from_its_own_stats_manager():
    """The bridge monkeypatch wires the IPC callback onto EVERY BaseStatsManager at
    __init__ — including LikeOrchestration's own "like" manager, whose near-empty
    snapshot would overwrite the workflow's counters in the UI. The class must cut
    its callback at construction so an accidental increment can never publish."""
    from unittest.mock import MagicMock

    from taktik.core.social_media.instagram.actions.core.stats import BaseStatsManager

    original_init = BaseStatsManager.__init__
    published = []

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.set_on_stats_callback(lambda stats: published.append(stats))

    BaseStatsManager.__init__ = patched_init
    try:
        from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
            LikeOrchestration,
        )

        orchestration = LikeOrchestration(MagicMock())
        orchestration.stats_manager.increment('likes')
        assert published == [], "the 'like' module manager must never publish snapshots"
    finally:
        BaseStatsManager.__init__ = original_init
