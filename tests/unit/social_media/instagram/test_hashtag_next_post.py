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

    def human_scroll(self, direction, distance_ratio=None, **_kwargs):
        self.scrolls.append((direction, distance_ratio))


class _Host(HashtagPostDetectionMixin):
    """Mixin under test with the screen reduced to a list of successive signatures."""

    def __init__(self, signatures):
        self.device = _Device()
        # Signatures returned by successive reads of the screen.
        self._signatures = list(signatures)

        class _Log:
            def debug(self, *a, **k): pass
            def info(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass

        self.logger = _Log()

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
    ratios = [ratio for _direction, ratio in host.device.scrolls]
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
    assert [ratio for _d, ratio in host.device.scrolls] == list(_Host._NEXT_POST_RATIOS[:2])


def test_uses_the_signature_the_caller_already_read():
    """The caller has just read the counters — re-reading them costs a UI dump per post."""
    host = _Host(["99_9_False"])  # single read: the one AFTER the gesture

    assert host._swipe_to_next_post(known_signature="12_3_False") is True
    assert host._signatures == []


def test_unreadable_screen_is_not_a_proven_arrival():
    """An empty signature means "could not read", not "new post" — never claim success on it."""
    host = _Host(["12_3_False", "", "", ""])

    assert host._swipe_to_next_post() is False


def test_signature_of_avoids_a_second_read():
    host = _Host([])

    assert host._signature_of({'likes_count': 76, 'comments_count': 3, 'is_reel': False}) == "76_3_False"
    assert host._signature_of(None) is None
