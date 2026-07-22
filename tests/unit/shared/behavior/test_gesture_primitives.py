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


def test_long_drag_falls_back_to_swipe_points_without_using_raw_drag(monkeypatch):
    _patch_path(monkeypatch)
    raw = _RawPoints()
    host = _Host(raw)

    assert host._long_drag("up") is True

    assert len(raw.calls) == 1
    assert raw.calls[0][0] == _PATH
    assert raw.drag_calls == []


def test_velocity_scale_changes_the_physical_drag_duration(monkeypatch):
    _patch_path(monkeypatch)
    monkeypatch.setattr(gp.random, "uniform", lambda lower, _upper: lower)
    slow_raw = _RawPoints()
    fast_raw = _RawPoints()

    assert _Host(slow_raw)._long_drag("up", velocity_scale=0.8) is True
    assert _Host(fast_raw)._long_drag("up", velocity_scale=1.2) is True

    slow_segment_duration = slow_raw.calls[0][1]
    fast_segment_duration = fast_raw.calls[0][1]
    assert slow_segment_duration > fast_segment_duration


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
