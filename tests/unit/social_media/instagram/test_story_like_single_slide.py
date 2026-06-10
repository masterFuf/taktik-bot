"""Story watch loop: story-likes are PROPORTIONAL to the slide count (read at open),
bounded by the watch budget, with a safe ≤1 fallback when the slide count is unreadable.

Drives `InteractionEngineMixin._view_stories_on_current_profile` with a fake device so we
can assert the like count and positions without a real story viewer.
"""

import types

import taktik.core.social_media.instagram.actions.core.base_business.interaction_engine as ie
from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (
    InteractionEngineMixin,
)


class _Detection:
    def __init__(self, slides, report_total=True):
        self._slides = slides
        self._report_total = report_total
        self._open_calls = 0

    def has_stories(self):
        return self._slides > 0

    def is_story_viewer_open(self):
        self._open_calls += 1
        return self._open_calls <= self._slides

    def get_story_count_from_viewer(self):
        # (current, total). When we don't report a total, mimic an unreadable content-desc.
        return (1, self._slides) if self._report_total else (0, 0)

    def get_story_viewer_metadata(self):
        return {}


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
    def __init__(self, slides, report_total=True):
        self.detection_actions = _Detection(slides, report_total)
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


def _run(monkeypatch, *, slides, do_story_like=True, max_story_likes=3,
         fallback_like_slot=-1, max_stories=10, report_total=True,
         count=None, slots=None):
    monkeypatch.setattr(ie.time, "sleep", lambda _s: None)
    monkeypatch.setattr(ie.random, "uniform", lambda a, b: a)
    # Make the proportional sampling deterministic when the test wants exact positions.
    if count is not None:
        monkeypatch.setattr(ie, "sample_story_like_count", lambda *a, **k: count)
    if slots is not None:
        monkeypatch.setattr(ie, "sample_story_like_slots", lambda *a, **k: list(slots))
    host = _Host(slides, report_total)
    res = host._view_stories_on_current_profile(
        "u", do_story_like=do_story_like, max_story_likes=max_story_likes,
        fallback_like_slot=fallback_like_slot, max_stories=max_stories,
    )
    return host, res


def test_proportional_likes_multiple_varied_slides(monkeypatch):
    # 12-slide story, plan 3 likes at varied slots → exactly 3 likes (not all 12).
    host, res = _run(monkeypatch, slides=12, max_stories=12, count=3, slots=[0, 4, 8])
    assert host.click_actions.like_calls == 3
    assert res["stories_liked"] == 3
    assert res["stories_viewed"] == 12


def test_no_like_when_story_like_disabled(monkeypatch):
    host, res = _run(monkeypatch, slides=6, do_story_like=False)
    assert host.click_actions.like_calls == 0
    assert res["stories_liked"] == 0


def test_unknown_slide_total_falls_back_to_single_like(monkeypatch):
    # Slide count unreadable → safe legacy fallback: at most ONE like at the fallback slot.
    host, res = _run(monkeypatch, slides=6, report_total=False, fallback_like_slot=2)
    assert host.click_actions.like_calls == 1
    assert res["stories_liked"] == 1


def test_unknown_total_no_fallback_slot_means_no_like(monkeypatch):
    host, res = _run(monkeypatch, slides=6, report_total=False, fallback_like_slot=-1)
    assert host.click_actions.like_calls == 0


def test_likes_bounded_by_watch_budget(monkeypatch):
    # 20-slide story but watch budget 3 → we can never like more than what we watch.
    host, res = _run(monkeypatch, slides=20, max_stories=3, count=3, slots=[0, 1, 2])
    assert res["stories_viewed"] == 3
    assert host.click_actions.like_calls == 3


def test_fallback_last_slide_when_planned_slots_unreached(monkeypatch):
    # Planned slot 4 but only 2 slides viewable → still leaves exactly one like (on the last).
    host, res = _run(monkeypatch, slides=2, count=1, slots=[4])
    assert host.click_actions.like_calls == 1
    assert res["stories_liked"] == 1
