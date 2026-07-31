"""HashtagPostDetectionMixin._swipe_to_next_post — an advance is only true once the post changed.

The blind version scrolled half a screen and reported success whatever happened. On a reel
(full screen) or a long-caption post that travel is not enough: the caller re-read the SAME
post, judged it already processed, scrolled again, and spent its whole post budget on one
post before opening the likers of a post it had just rejected.
"""

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.hashtag.mixins.post_detection import (
    HashtagPostDetectionMixin,
)


class _Device:
    def __init__(self):
        self.scrolls = []

    def human_scroll(self, direction, distance_ratio=None, coast=False, **_kwargs):
        self.scrolls.append((direction, distance_ratio, coast))


class _Host(HashtagPostDetectionMixin):
    """Mixin under test with the screen reduced to a list of successive signatures."""

    def __init__(self, signatures, is_reel=False):
        self.device = _Device()
        # Signatures returned by successive reads of the screen.
        self._signatures = list(signatures)
        self._is_reel = is_reel

        class _Log:
            def debug(self, *a, **k): pass
            def info(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass

        self.logger = _Log()

    def _is_reel_post(self):
        return self._is_reel

    def _current_post_signature(self):
        return self._signatures.pop(0) if self._signatures else "stuck"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.workflows.hashtag.mixins.post_detection.time.sleep",
        lambda *_a, **_k: None,
    )


def test_reports_failure_when_the_post_never_changes():
    host = _Host(["12_3_False"] * 6)

    assert host._swipe_to_next_post() is False
    # Every configured travel was tried, each one larger than the last.
    ratios = [ratio for _direction, ratio, _coast in host.device.scrolls]
    assert ratios == list(_Host._NEXT_POST_RATIOS)
    assert ratios == sorted(ratios)


def test_stops_at_the_first_gesture_that_actually_moves():
    host = _Host(["12_3_False", "40_2_True"])

    assert host._swipe_to_next_post() is True
    assert len(host.device.scrolls) == 1


def test_retries_further_when_the_first_travel_falls_short():
    # Same post after the first scroll (too short), new post after the second.
    host = _Host(["12_3_False", "12_3_False", "88_7_False"])

    assert host._swipe_to_next_post() is True
    assert [ratio for _d, ratio, _c in host.device.scrolls] == list(_Host._NEXT_POST_RATIOS[:2])


def test_uses_the_signature_the_caller_already_read():
    """The caller has just read the counters — re-reading them costs a UI dump per post."""
    host = _Host(["99_9_False"])  # single read: the one AFTER the gesture

    assert host._swipe_to_next_post(known_signature="12_3_False") is True
    assert host._signatures == []


def test_unreadable_screen_is_not_a_proven_arrival():
    """An empty signature means "could not read", not "new post" — never claim success on it."""
    host = _Host(["12_3_False", "", "", ""])

    assert host._swipe_to_next_post() is False


def test_a_reel_is_advanced_with_a_fling_not_a_controlled_scroll():
    """A reel viewer is a pager: below its velocity threshold it springs BACK to the current
    reel. A 1:1 controlled curve never crosses that threshold — which is what "it takes
    several tries to change reel" looked like on the phone. `coast=True` is the real fling."""
    host = _Host(["12_3_True_alice", "40_2_True_bob"], is_reel=True)

    assert host._swipe_to_next_post() is True
    direction, ratio, coast = host.device.scrolls[0]
    assert (direction, coast) == ("down", True)
    assert ratio == _Host._NEXT_REEL_RATIOS[0]


def test_reel_travels_stay_inside_the_flick_envelope():
    """A flick clamps its finger travel to 0.45h (`_strong_flick`, dist_cap_h=0.45). Ask for
    more and every attempt clamps to the SAME gesture — an escalation that escalates nothing,
    which is indistinguishable from the bug it is meant to fix. The content coasts ~2.5-4x
    the finger, so 0.30h already moves about a screen of reel."""
    assert max(_Host._NEXT_REEL_RATIOS) <= 0.45
    assert list(_Host._NEXT_REEL_RATIOS) == sorted(set(_Host._NEXT_REEL_RATIOS))


def test_a_regular_post_keeps_the_controlled_gesture():
    """A post detail is a LIST, and the extractor counts one advance as one post: a coasting
    fling would land two posts further and make it read the wrong one."""
    host = _Host(["12_3_False", "88_7_False"], is_reel=False)

    assert host._swipe_to_next_post() is True
    assert host.device.scrolls == [("down", _Host._NEXT_POST_RATIOS[0], False)]


def test_signature_of_avoids_a_second_read():
    host = _Host([])

    assert host._signature_of({'likes_count': 76, 'comments_count': 3, 'is_reel': False}) == "76_3_False"
    assert host._signature_of(None) is None
