"""Low-level drag execution must move before waiting and keep the historical fallbacks."""

import math
import random

import taktik.core.shared.behavior.gesture_primitives as gp


_PATH = [[270, 1900], [285, 1680], [305, 1180], [320, 420]]


class _Log:
    def debug(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class _Touch:
    def __init__(self):
        self.events = []

    def down(self, x, y):
        self.events.append(("down", x, y))
        return self

    def move(self, x, y):
        self.events.append(("move", x, y))
        return self

    def sleep(self, seconds):
        self.events.append(("sleep", seconds))
        return self

    def up(self, x, y):
        self.events.append(("up", x, y))
        return self


class _RawTouch:
    def __init__(self):
        self.touch = _Touch()
        self.drag_calls = []

    def drag(self, *args, **kwargs):
        self.drag_calls.append((args, kwargs))


class _RawPoints:
    def __init__(self):
        self.calls = []
        self.drag_calls = []

    def swipe_points(self, path, duration):
        self.calls.append((path, duration))

    def drag(self, *args, **kwargs):
        self.drag_calls.append((args, kwargs))


class _JsonRpc:
    def __init__(self, owner):
        self._owner = owner

    def swipePoints(self, flat, steps):
        self._owner.point_calls.append((flat, steps))


class _RawJsonRpc:
    """A device exposing the preferred entry point: the whole path in one round trip."""

    def __init__(self):
        self.point_calls = []
        self.drag_calls = []
        self.jsonrpc = _JsonRpc(self)


class _RawBare:
    pass


class _RawSwipe:
    def __init__(self):
        self.calls = []

    def swipe(self, x1, y1, x2, y2, duration=0.5):
        self.calls.append((x1, y1, x2, y2, duration))


class _Device:
    def __init__(self, raw):
        self._device = raw
        self.swipes = []

    def swipe_coordinates(self, *args):
        self.swipes.append(args)


class _Host(gp.GestureMixin):
    screen_width = 1080
    screen_height = 2280

    def __init__(self, raw, exclusions=()):
        self.device = _Device(raw)
        self.logger = _Log()
        self.exclusions = exclusions

    def _gesture_start_exclusion_bounds(self):
        return self.exclusions

    @staticmethod
    def _gesture_fallback_safe_x_band():
        return (0.46, 0.70)


def _patch_path(monkeypatch):
    monkeypatch.setattr(gp, "sample_swipe", lambda *_args, **_kwargs: ([p[:] for p in _PATH], 0.6))
    monkeypatch.setattr(gp.time, "sleep", lambda _seconds: None)


def test_long_drag_moves_immediately_before_any_sleep(monkeypatch):
    _patch_path(monkeypatch)
    raw = _RawTouch()
    host = _Host(raw)

    assert host._long_drag("up") is True

    events = raw.touch.events
    assert events[0][0] == "down"
    assert events[1][0] == "move"  # no dwell between DOWN and the first MOVE
    first_distance = math.hypot(events[1][1] - events[0][1], events[1][2] - events[0][2])
    assert first_distance >= 0.03 * host.screen_height
    assert events[-1] == ("up", _PATH[-1][0], _PATH[-1][1])
    assert raw.drag_calls == []


def test_controlled_human_swipe_also_moves_before_sleep(monkeypatch):
    _patch_path(monkeypatch)
    raw = _RawTouch()
    host = _Host(raw)

    assert host._human_swipe("up", controlled=True) is True

    assert [event[0] for event in raw.touch.events[:3]] == ["down", "move", "sleep"]
    assert raw.touch.events[-1][0] == "up"


def test_controlled_human_swipe_allows_long_one_to_one_travel(monkeypatch):
    captured = {}

    def fake_sample(*_args, **kwargs):
        captured.update(kwargs)
        return [point[:] for point in _PATH], 0.6

    monkeypatch.setattr(gp, "sample_swipe", fake_sample)
    monkeypatch.setattr(gp.time, "sleep", lambda _seconds: None)

    assert _Host(_RawTouch())._human_swipe(
        "up", distance_px=0.68 * 2280, controlled=True
    ) is True

    assert captured["dist_cap_h"] == 0.95


def test_slop_exit_distance_varies_above_the_floor():
    moves_a = gp._touch_move_path(_PATH, 2280, rng=random.Random(1))
    moves_b = gp._touch_move_path(_PATH, 2280, rng=random.Random(2))

    distances = [math.hypot(move[0] - _PATH[0][0], move[1] - _PATH[0][1])
                 for move in (moves_a[0], moves_b[0])]
    assert all(distance >= 0.03 * 2280 for distance in distances)
    assert round(distances[0]) != round(distances[1])


def test_touch_path_distributes_the_complete_duration():
    host = _Host(_RawBare())
    touch = _Touch()

    host._execute_touch_path(touch, _PATH, 0.6)

    sleeps = [event[1] for event in touch.events if event[0] == "sleep"]
    assert abs(sum(sleeps) - 0.6) < 1e-9


def test_long_drag_hands_the_path_to_the_device_without_using_raw_drag(monkeypatch):
    """One call carrying a densified path, and still never `raw.drag`.

    The path is resampled before it goes down: paced from the PC, the sampler's 4 points WERE the
    whole gesture (4 events, ~8 Hz, 265px jumps). Handed over whole, the device injects one move
    per segment every 5 ms, so the segment count is the duration.
    """
    _patch_path(monkeypatch)
    raw = _RawPoints()
    host = _Host(raw)

    assert host._long_drag("up") is True

    assert len(raw.calls) == 1
    points, _ = raw.calls[0]
    assert raw.drag_calls == []
    # Densified well past the 4 sampled points. The exact count is deliberately NOT asserted: it is
    # duration / measured cost per step, so it follows the phone (22 events on a Pixel 3a at 18 ms,
    # ~80 on a device that really honours 5 ms).
    assert len(points) >= 5 * len(_PATH)
    assert points[0] == _PATH[0]                  # the guarded start must stay exact
    assert points[-1] == _PATH[-1]                # and so must the landing point


def test_device_path_never_asks_for_a_single_step(monkeypatch):
    """`UiDevice.swipe(Point[], steps)` injects `steps - 1` moves per segment.

    At 1 it injects NONE and the drag silently becomes a down/up pair — a tap, which on a feed
    opens whatever sits under the finger. uiautomator2 guards its own `swipe` with `max(2, steps)`
    but NOT `swipe_points`, so the floor has to be ours.
    """
    _patch_path(monkeypatch)
    raw = _RawJsonRpc()
    host = _Host(raw)

    assert host._long_drag("up") is True

    _, steps = raw.point_calls[0]
    assert steps >= 2


def test_velocity_scale_changes_the_physical_drag_duration(monkeypatch):
    """Duration now lives in the POINT COUNT, not in a per-segment delay.

    The device spends a fixed 5 ms per step, so a slower gesture is a longer path, and the
    per-segment duration it is handed is deliberately constant.
    """
    _patch_path(monkeypatch)
    monkeypatch.setattr(gp.random, "uniform", lambda lower, _upper: lower)
    slow_raw = _RawPoints()
    fast_raw = _RawPoints()

    assert _Host(slow_raw)._long_drag("up", velocity_scale=0.8) is True
    assert _Host(fast_raw)._long_drag("up", velocity_scale=1.2) is True

    assert len(slow_raw.calls[0][0]) > len(fast_raw.calls[0][0])


def test_step_cost_is_learned_from_the_first_gesture(monkeypatch):
    """The event count must follow what a step really COSTS on this phone, not the nominal 5 ms.

    UiAutomator sleeps 5 ms per step, but injecting the event costs more on top and how much is a
    property of the device: 18.1 ms measured on a Pixel 3a, where a path sized for 5 ms ran 3.6x
    long. Seeding an average and blending later readings would need a dozen gestures to converge,
    so the FIRST measurement replaces the seed outright.
    """
    raw = _RawPoints()

    assert gp._step_cost(raw) == gp._DEVICE_STEP_SEED
    gp._observe_step_cost(raw, 0.0181)
    assert abs(gp._step_cost(raw) - 0.0181) < 1e-6

    # A later reading is smoothed, so one slow call cannot swing the pacing...
    gp._observe_step_cost(raw, 0.030)
    assert 0.018 < gp._step_cost(raw) < 0.024
    # ...and an absurd one is clamped rather than trusted.
    for _ in range(20):
        gp._observe_step_cost(raw, 5.0)
    assert gp._step_cost(raw) <= gp._STEP_COST_BOUNDS[1]


def test_controlled_gesture_velocity_stays_in_the_human_band(monkeypatch):
    """A controlled gesture's duration must be coherent with the distance it covers.

    `sample_swipe` reuses the duration of a randomly chosen REAL swipe, rescaled by at most ±40%
    for distance, so the same 0.62h request came out anywhere between 169 ms (8000 px/s — a flick,
    not an accompanied drag) and 850 ms. Sampling stays the source of variability; only the two
    impossible tails are trimmed.
    """
    travel = 1480.0
    low, high = gp._CONTROLLED_VEL_RANGE
    for sampled in (0.05, 0.3, 0.6, 5.0):
        duration = gp._controlled_duration(sampled, travel)
        assert low - 1 <= travel / duration <= high + 1


def test_long_drag_falls_back_to_facade_swipe_coordinates(monkeypatch):
    _patch_path(monkeypatch)
    host = _Host(_RawBare())

    assert host._long_drag("up") is True

    assert len(host.device.swipes) == 1
    assert host.device.swipes[0][:4] == (270, 1900, 320, 420)


def test_requested_share_start_is_relocated_before_touch_down(monkeypatch):
    _patch_path(monkeypatch)
    raw = _RawTouch()
    share = (190, 1800, 330, 1980)
    host = _Host(raw, exclusions=[share])

    assert host._long_drag("up", start_point=(250, 1900), guard_start=True) is True

    state = host._last_gesture_start
    assert state["requested"] == (250, 1900)
    assert state["adjusted"] is True
    assert state["source"] == "ui_bounds"
    final_x, final_y = state["final"]
    assert not (share[0] <= final_x <= share[2] and share[1] <= final_y <= share[3])
    assert raw.touch.events[0] == ("down", final_x, final_y)


def test_missing_dump_uses_ratio_based_safe_band():
    host = _Host(_RawBare(), exclusions=None)
    path = [[200, 1800], [220, 600]]

    guarded = host._prepare_gesture_path(path, guard_start=True)

    assert 0.46 * host.screen_width <= guarded[0][0] <= 0.70 * host.screen_width
    assert host._last_gesture_start["source"] == "fallback_band"
    assert host._last_gesture_start["adjusted"] is True


def test_horizontal_swipe_stays_inside_requested_media_bounds(monkeypatch):
    monkeypatch.setattr(gp.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(gp.random, "uniform", lambda lower, upper: (lower + upper) / 2)
    raw = _RawSwipe()
    host = _Host(raw)
    bounds = (120, 360, 960, 1760)

    assert host._human_horizontal_swipe(
        "left", bounds=bounds, distance_scale=1.04, velocity_scale=0.90
    ) is True

    x1, y1, x2, y2, _duration = raw.calls[0]
    assert bounds[0] <= x1 <= bounds[2]
    assert bounds[0] <= x2 <= bounds[2]
    assert bounds[1] <= y1 <= bounds[3]
    assert bounds[1] <= y2 <= bounds[3]
    assert x2 < x1


def test_horizontal_velocity_scale_changes_duration(monkeypatch):
    monkeypatch.setattr(gp.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(gp.random, "uniform", lambda lower, upper: (lower + upper) / 2)
    slow_raw, fast_raw = _RawSwipe(), _RawSwipe()

    assert _Host(slow_raw)._human_horizontal_swipe("left", velocity_scale=0.8) is True
    assert _Host(fast_raw)._human_horizontal_swipe("left", velocity_scale=1.2) is True

    assert slow_raw.calls[0][4] > fast_raw.calls[0][4]
