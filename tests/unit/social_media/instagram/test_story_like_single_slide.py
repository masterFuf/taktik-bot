"""Story watch loop likes AT MOST ONE slide (never all) — the rare, single story-like.

Drives `InteractionEngineMixin._view_stories_on_current_profile` with a fake device so we
can assert the like count and position without a real story viewer.
"""

import types

import taktik.core.social_media.instagram.actions.core.base_business.interaction_engine as ie
from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (
    InteractionEngineMixin,
)


class _Detection:
    def __init__(self, slides):
        self._slides = slides
        self._open_calls = 0

    def has_stories(self):
        return self._slides > 0

    def is_story_viewer_open(self):
        # Open while there are slides left to view.
        self._open_calls += 1
        return self._open_calls <= self._slides


class _Clicks:
    def __init__(self):
        self.like_calls = 0

    def click_story_ring(self):
        return True

    def like_story(self):
        self.like_calls += 1
        return True

    def close_story(self):
        return True


class _Nav:
    def __init__(self, slides):
        self._left = slides

    def navigate_to_next_story(self):
        self._left -= 1
        return self._left > 0


class _Host(InteractionEngineMixin):
    def __init__(self, slides):
        self.detection_actions = _Detection(slides)
        self.click_actions = _Clicks()
        self.nav_actions = _Nav(slides)
        self.device = types.SimpleNamespace(press=lambda *_a, **_k: None)

        class _Log:
            def debug(self, *a, **k): pass
            def error(self, *a, **k): pass
            def info(self, *a, **k): pass
        self.logger = _Log()

    def _human_like_delay(self, *_a, **_k):
        return None

    def _record_action(self, *_a, **_k):
        return None


def _run(slides, like_slot, monkeypatch):
    monkeypatch.setattr(ie.time, "sleep", lambda _s: None)
    monkeypatch.setattr(ie.random, "uniform", lambda a, b: a)
    host = _Host(slides)
    res = host._view_stories_on_current_profile("u", like_slot=like_slot, max_stories=10)
    return host, res


def test_likes_exactly_one_slide_at_slot(monkeypatch):
    host, res = _run(slides=6, like_slot=2, monkeypatch=monkeypatch)
    assert host.click_actions.like_calls == 1          # ONE like, never all 6
    assert res["stories_liked"] == 1
    assert res["stories_viewed"] == 6


def test_no_like_when_slot_negative(monkeypatch):
    host, res = _run(slides=5, like_slot=-1, monkeypatch=monkeypatch)
    assert host.click_actions.like_calls == 0
    assert res["stories_liked"] == 0


def test_fallback_likes_last_slide_when_story_shorter_than_slot(monkeypatch):
    # Planned slot 4 but only 2 slides → still leaves exactly one like (on the last).
    host, res = _run(slides=2, like_slot=4, monkeypatch=monkeypatch)
    assert host.click_actions.like_calls == 1
    assert res["stories_liked"] == 1


def test_never_likes_more_than_one_even_long_story(monkeypatch):
    host, res = _run(slides=12, like_slot=0, monkeypatch=monkeypatch)
    assert host.click_actions.like_calls == 1
