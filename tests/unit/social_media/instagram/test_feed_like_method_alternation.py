"""Liking a feed post alternates between the like button and an image double-tap
(a human doesn't always use the same method), and never re-likes an already-liked
post. Part of the P1-taps humanization
(`taktik-docs/bot/security/humanization-master-plan.md`).
"""

import random
import types

import taktik.core.social_media.instagram.actions.business.workflows.feed.post_actions as pa
from taktik.core.social_media.instagram.actions.business.workflows.feed.post_actions import (
    FeedPostActionsMixin,
)


def test_method_choice_is_probabilistic():
    rng = random.Random(0)
    n = 4000
    frac = sum(pa._should_double_tap_like(rng=rng) for _ in range(n)) / n
    assert 0.40 < frac < 0.50  # ~45% double-tap, the rest the like button


class _El:
    def __init__(self, exists=False, content_desc=""):
        self.exists = exists
        self.attrib = {"content-desc": content_desc}


class _FeedSel:
    like_button = ["like_sel"]
    already_liked_indicators = ["already_sel"]


class _Device:
    def __init__(self, elements):
        self._elements = elements
        self.double_tap_calls = []
        self.double_click_calls = []

    def xpath(self, selector):
        return self._elements.get(selector, _El(exists=False))

    @property
    def info(self):
        return {"displayWidth": 1080, "displayHeight": 1920}

    def human_double_tap(self, bounds, *, rng=None):
        self.double_tap_calls.append(tuple(bounds))
        return (1, 2)

    def double_click(self, x, y):
        self.double_click_calls.append((x, y))


class _Probe(FeedPostActionsMixin):
    def __init__(self, elements):
        self.device = _Device(elements)
        self._feed_sel = _FeedSel()
        self.logger = types.SimpleNamespace(debug=lambda *a, **k: None)
        self.human_tap_calls = []

    def _human_tap_element(self, element):
        self.human_tap_calls.append(element)
        return True

    def _human_like_delay(self, kind):
        pass


def test_already_liked_is_skipped():
    p = _Probe({"like_sel": _El(exists=True, content_desc="Unlike")})
    assert p._like_current_post() is False
    assert p.device.double_tap_calls == [] and p.human_tap_calls == []


def test_button_method_human_taps_the_button(monkeypatch):
    monkeypatch.setattr(pa, "_should_double_tap_like", lambda rng=None: False)
    p = _Probe({"like_sel": _El(exists=True, content_desc="Like")})
    assert p._like_current_post() is True
    assert len(p.human_tap_calls) == 1  # tapped the button (varied point)
    assert p.device.double_tap_calls == []


def test_double_tap_method_double_taps_the_image(monkeypatch):
    monkeypatch.setattr(pa, "_should_double_tap_like", lambda rng=None: True)
    p = _Probe({"like_sel": _El(exists=True, content_desc="Like")})
    assert p._like_current_post() is True
    assert len(p.device.double_tap_calls) == 1  # double-tapped the image band
    assert p.human_tap_calls == []


def test_no_like_button_forces_double_tap(monkeypatch):
    # Even if chance picks the button, no button visible → must double-tap.
    monkeypatch.setattr(pa, "_should_double_tap_like", lambda rng=None: False)
    p = _Probe({})
    assert p._like_current_post() is True
    assert len(p.device.double_tap_calls) == 1
    assert p.human_tap_calls == []
