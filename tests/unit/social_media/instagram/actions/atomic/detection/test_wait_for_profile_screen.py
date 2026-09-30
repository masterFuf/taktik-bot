"""On a slow/tethered connection the profile page loads several seconds after the tap. The bot must
WAIT for it instead of a single immediate check that wrongly skips the follower (observed case:
17/20 profiles skipped without ever loading).
"""

from taktik.core.social_media.instagram.actions.atomic.detection.screen_detection import ScreenDetectionMixin


def _detector(results):
    """A ScreenDetectionMixin whose is_on_profile_screen yields the given booleans in order."""
    d = object.__new__(ScreenDetectionMixin)
    d._screen_signal_snapshot_cache = {'stale': True}
    seq = iter(results)
    d.is_on_profile_screen = lambda: next(seq, results[-1])  # type: ignore[assignment]
    return d


def test_returns_true_once_the_profile_loads(monkeypatch):
    import taktik.core.social_media.instagram.actions.atomic.detection.screen_detection as mod
    monkeypatch.setattr(mod.time, 'sleep', lambda *_: None)
    # Not loaded on the first two polls, then loaded.
    d = _detector([False, False, True])
    assert d.wait_for_profile_screen(timeout=8.0, interval=0.1) is True
    # The batched screen-signal cache is cleared so each poll reads fresh.
    assert d._screen_signal_snapshot_cache is None


def test_returns_false_when_it_never_loads(monkeypatch):
    import taktik.core.social_media.instagram.actions.atomic.detection.screen_detection as mod
    monkeypatch.setattr(mod.time, 'sleep', lambda *_: None)
    d = _detector([False])
    # timeout=0 => one check, still not loaded => give up (no infinite loop).
    assert d.wait_for_profile_screen(timeout=0.0, interval=0.1) is False


def test_returns_true_immediately_when_already_on_profile(monkeypatch):
    import taktik.core.social_media.instagram.actions.atomic.detection.screen_detection as mod
    monkeypatch.setattr(mod.time, 'sleep', lambda *_: (_ for _ in ()).throw(AssertionError('should not sleep')))
    d = _detector([True])
    assert d.wait_for_profile_screen(timeout=8.0) is True
