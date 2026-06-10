"""StoryBusiness leaves AT MOST one like / one reaction per story (not one per slide).

Covers `_plan_story_engagement` (the once-per-story decision) and `view_profile_stories`
(the ≤1-like enforcement) without a real device.
"""

import random
import types

import taktik.core.social_media.instagram.actions.business.actions.story as story_mod
from taktik.core.social_media.instagram.actions.business.actions.story import StoryBusiness


def _make_business():
    # Bypass __init__ (heavy collaborators); set only what the methods touch.
    biz = StoryBusiness.__new__(StoryBusiness)
    biz.default_config = {
        'max_stories_per_profile': 5, 'view_duration_range': (0, 0),
        'navigation_delay_range': (0, 0), 'like_probability': 0.3,
        'reaction_probability': 0.0,
    }

    class _Log:
        def debug(self, *a, **k): pass
        def info(self, *a, **k): pass
        def error(self, *a, **k): pass
    biz.logger = _Log()
    return biz


# ─── _plan_story_engagement ──────────────────────────────────────────────────

def test_plan_likes_one_slot_when_certain(monkeypatch):
    biz = _make_business()
    like_slot, react_slot = biz._plan_story_engagement(
        {'like_probability': 1.0, 'reaction_probability': 0.0}, max_stories=6)
    assert 0 <= like_slot <= 5
    assert react_slot == -1


def test_plan_no_engagement_when_zero(monkeypatch):
    biz = _make_business()
    assert biz._plan_story_engagement({'like_probability': 0.0, 'reaction_probability': 0.0}, 6) == (-1, -1)


def test_plan_reaction_independent(monkeypatch):
    biz = _make_business()
    _, react_slot = biz._plan_story_engagement(
        {'like_probability': 0.0, 'reaction_probability': 1.0}, max_stories=4)
    assert 0 <= react_slot <= 3


# ─── view_profile_stories: ≤ 1 like over a long story ────────────────────────

class _Nav:
    def navigate_to_profile(self, _u): return True
    def navigate_to_next_story(self): return True


class _Detect:
    def __init__(self, slides):
        self._slides = slides
        self._open = 0
    def has_stories(self): return True
    def get_story_count_from_viewer(self): return (1, self._slides)
    def get_story_viewer_metadata(self): return {'title': 'friend', 'is_ad': False}
    def is_story_viewer_open(self):
        self._open += 1
        return self._open <= self._slides


class _Clicks:
    def __init__(self):
        self.like_calls = 0
    def click_story_ring(self): return True
    def like_story(self):
        self.like_calls += 1
        return True
    def close_story(self): return True


def test_view_profile_stories_likes_at_most_once(monkeypatch):
    monkeypatch.setattr(story_mod.time, "sleep", lambda _s: None)
    monkeypatch.setattr(story_mod.random, "uniform", lambda a, b: a)
    monkeypatch.setattr(story_mod.random, "random", lambda: 0.0)   # always plan a like

    biz = _make_business()
    biz.nav_actions = _Nav()
    biz.detection_actions = _Detect(slides=6)
    biz.click_actions = _Clicks()
    biz._human_like_delay = lambda *_a, **_k: None
    biz._press_back = lambda *_a, **_k: None
    biz._record_action = lambda *_a, **_k: None

    stats = biz.view_profile_stories("friend", max_stories=6)
    assert biz.click_actions.like_calls == 1     # ONE like over 6 slides, never 6
    assert stats['stories_liked'] == 1
    assert stats['stories_viewed'] == 6
