"""`human_scroll_raw(precise=True)` asks for the controlled drag that covers the distance asked.

Without it the sampled flick envelope caps the travel at 34% of the screen whatever the ratio:
on a phone, 0.4 and 0.8 both moved about 3 rows of a follow list (2026-09-24). The default is
left as it is for the other callers.
"""

import types

import taktik.core.shared.behavior.gesture_primitives as gestures
from taktik.core.shared.behavior.gesture import sample_swipe


def _recording_host(monkeypatch):
    calls = []
    host = types.SimpleNamespace(
        screen_height=2000,
        _human_swipe=lambda **kwargs: calls.append(kwargs) or True,
        _strong_flick=lambda **kwargs: calls.append({"flick": True, **kwargs}) or True,
    )
    monkeypatch.setattr(gestures, "_raw_host", lambda raw, logger=None: host)
    return calls


def test_precise_asks_for_the_controlled_drag(monkeypatch):
    calls = _recording_host(monkeypatch)

    gestures.human_scroll_raw(object(), "down", distance_ratio=0.8, precise=True)

    assert calls[-1]["controlled"] is True
    assert calls[-1]["distance_px"] == 1600


def test_the_default_is_unchanged_for_the_other_callers(monkeypatch):
    calls = _recording_host(monkeypatch)

    gestures.human_scroll_raw(object(), "down", distance_ratio=0.8)

    assert calls[-1]["controlled"] is False


def test_the_default_envelope_caps_the_travel_and_the_controlled_one_does_not():
    capped, _ = sample_swipe(1080, 2000, direction="up", distance_px=1600)
    controlled, _ = sample_swipe(1080, 2000, direction="up", distance_px=1600, dist_cap_h=0.95)

    assert abs(capped[-1][1] - capped[0][1]) <= 0.34 * 2000 + 1
    assert abs(controlled[-1][1] - controlled[0][1]) > 0.34 * 2000
