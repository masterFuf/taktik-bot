"""`human_scroll_raw(precise=True)` asks for the controlled drag that covers the distance asked.

Without it the sampled flick envelope caps the travel at 34% of the screen whatever the ratio:
on a phone, 0.4 and 0.8 both moved about 3 rows of a follow list (2026-09-24). The default is
left as it is for the other callers.
"""

import random
import types

import pytest
from loguru import logger

import taktik.core.shared.behavior.gesture_primitives as gestures
from taktik.core.shared.behavior.gesture import FULL_REACH_H, load_calibration, sample_swipe


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


def test_the_default_envelope_caps_the_travel():
    for seed in range(SEEDS):
        path, _ = sample_swipe(1080, 2000, direction="up", distance_px=1600,
                               rng=random.Random(seed))
        assert abs(path[-1][1] - path[0][1]) <= 0.34 * 2000 + 1


# A controlled swipe used to draw its start first and cut the travel at the screen edge: asked
# for 0.7 of the screen, 58 % of the gestures covered less than 95 % of it, and the content
# follows the finger 1:1 (Instagram 410, grid and feed: content = finger - 22 to 45 px).
SEEDS = 300
SCREENS = [(1080, 2160), (1080, 2400)]
ROOM_H = {"up": 0.81, "down": 0.86}


def _travels(w, h, direction, ratio, **kwargs):
    for seed in range(SEEDS):
        path, _ = sample_swipe(w, h, direction=direction, distance_px=ratio * h,
                               dist_cap_h=FULL_REACH_H, rng=random.Random(seed), **kwargs)
        yield path, abs(path[-1][1] - path[0][1])


@pytest.mark.parametrize("w, h", SCREENS)
@pytest.mark.parametrize("direction", ["up", "down"])
@pytest.mark.parametrize("ratio", [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8])
def test_a_request_that_fits_the_room_is_covered(w, h, direction, ratio):
    room = ROOM_H[direction] * h
    if ratio * h > room:
        pytest.skip("longer than the room: see the bounded case")
    for _, travel in _travels(w, h, direction, ratio):
        assert 0.95 * ratio * h - 1 <= travel <= ratio * h + 1


@pytest.mark.parametrize("w, h", SCREENS)
@pytest.mark.parametrize("direction, ratio", [("up", 0.84), ("up", 0.95), ("down", 0.9)])
def test_a_request_longer_than_the_room_is_bounded_to_it_and_logged(w, h, direction, ratio):
    room = ROOM_H[direction] * h
    messages = []
    sink = logger.add(lambda m: messages.append(m.record["message"]), level="DEBUG")
    try:
        travels = [travel for _, travel in _travels(w, h, direction, ratio)]
    finally:
        logger.remove(sink)
    assert all(0.95 * room - 1 <= travel <= room + 1 for travel in travels)
    assert len([m for m in messages if "bounded to the room" in m]) == SEEDS
    assert f"requested {round(ratio * h)} px" in messages[0]


def test_a_start_band_is_kept_and_the_travel_still_fits():
    w, h = 1080, 2400
    for path, travel in _travels(w, h, "up", 0.7, start_band=(0.78 * h, 0.85 * h)):
        assert 0.78 * h - 1 <= path[0][1] <= 0.85 * h + 1
        assert travel >= 0.95 * 0.7 * h - 1


def test_the_start_of_a_long_request_is_a_real_start():
    """Drawn among the recorded starts that leave room for the travel: the lowest strip where the
    travel still fits holds as many starts as the recorded ones put there, no pile-up on it."""
    w, h = 1080, 2400
    lowest = 0.04 + 0.95 * 0.7
    starts = [path[0][1] / h for path, _ in _travels(w, h, "up", 0.7)]
    real = [item["ny"] for item in load_calibration()["up"] if lowest <= item["ny"] <= 0.85]

    def strip_share(values):
        return sum(lowest <= y <= lowest + 0.04 for y in values) / len(values)

    assert strip_share(starts) <= strip_share(real) + 0.08
    assert len(set(round(y * h) for y in starts)) > SEEDS // 3
