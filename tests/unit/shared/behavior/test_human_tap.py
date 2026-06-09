"""Human tap point sampling — a tap must never land on the exact same pixel twice
(robotic), nor the dead centre, nor outside/on the rim of the target.

This is the geometry half of the P1 "humanise taps" workstream
(`taktik-docs/bot/security/humanization-master-plan.md`). The device execution lives
in `shared/device/facade.py::human_tap`; the *where to tap* logic is here, pure and
testable offline.
"""

import random

from taktik.core.shared.behavior.tap import sample_tap_point, sample_tap_down_ms


def test_point_inside_inner_margin():
    # 400x200 button at (100,500)-(500,700).
    bounds = (100, 500, 500, 700)
    lx, ty, rx, by = bounds
    rng = random.Random(1)
    for _ in range(500):
        x, y = sample_tap_point(bounds, rng=rng)
        # Strictly inside the element (never the rim / a neighbour).
        assert lx < x < rx, (x, bounds)
        assert ty < y < by, (y, bounds)


def test_points_vary_and_are_not_dead_centre():
    bounds = (0, 0, 300, 300)  # centre = (150, 150)
    rng = random.Random(2)
    points = [sample_tap_point(bounds, rng=rng) for _ in range(200)]
    unique = set(points)
    # Not a fixed point: lots of distinct taps.
    assert len(unique) > 100, len(unique)
    # Not glued to the dead centre.
    assert points.count((150, 150)) < 20


def test_distribution_centred_on_element():
    bounds = (0, 0, 400, 400)  # centre = (200, 200)
    rng = random.Random(3)
    xs, ys = [], []
    for _ in range(4000):
        x, y = sample_tap_point(bounds, rng=rng)
        xs.append(x)
        ys.append(y)
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    # Gaussian toward the centre → mean near 200, with spread (not a single point).
    assert 180 < mean_x < 220, mean_x
    assert 180 < mean_y < 220, mean_y
    assert max(xs) - min(xs) > 40  # there IS spread


def test_tiny_bounds_do_not_crash():
    for bounds in [(10, 10, 11, 11), (10, 10, 12, 13), (5, 5, 5, 5)]:
        x, y = sample_tap_point(bounds)
        lx, ty, rx, by = bounds
        # Clamp keeps it within the (degenerate) box.
        assert min(lx, rx) <= x <= max(lx, rx)
        assert min(ty, by) <= y <= max(ty, by)


def test_down_time_is_a_tap_not_a_long_press():
    rng = random.Random(4)
    vals = [sample_tap_down_ms(rng=rng) for _ in range(2000)]
    assert all(30.0 <= v <= 220.0 for v in vals)  # well under the ~400ms long-press threshold
    assert len(set(int(v) for v in vals)) > 50  # varies
    assert 50.0 < (sum(vals) / len(vals)) < 110.0  # quick-ish median
