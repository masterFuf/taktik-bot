"""`sample_within` draws again instead of clamping; `lognormal_with_mean` keeps its mean."""

import random
import statistics

import pytest

from taktik.core.shared.behavior.sampling import lognormal_with_mean, sample_within


class _Sequence:
    """A draw that returns the given values in order, and counts the calls."""

    def __init__(self, *values):
        self.values = list(values)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.values.pop(0)


def test_a_first_value_inside_the_bounds_is_kept_without_drawing():
    draw = _Sequence(0.5)
    assert sample_within(draw, 0.0, 1.0, first=0.25) == 0.25
    assert draw.calls == 0


def test_an_out_of_range_value_is_drawn_again_not_clamped():
    draw = _Sequence(1.7, -0.3, 0.6)
    assert sample_within(draw, 0.0, 1.0) == 0.6
    assert draw.calls == 3


def test_after_the_tries_the_fallback_is_a_uniform_draw_inside_the_bounds():
    rng = random.Random(3)
    values = [sample_within(lambda: 9.0, 0.0, 1.0, rng=rng, max_tries=4) for _ in range(2000)]
    assert all(0.0 <= v <= 1.0 for v in values)
    assert len({round(v, 3) for v in values}) > 500        # spread, not one value
    assert 0.45 < statistics.fmean(values) < 0.55


def test_the_edge_band_keeps_the_side_the_draws_were_missing():
    rng = random.Random(4)
    above = [sample_within(lambda: 9.0, 0.0, 1.0, rng=rng, max_tries=2, edge_band=0.1)
             for _ in range(1000)]
    below = [sample_within(lambda: -9.0, 0.0, 1.0, rng=rng, max_tries=2, edge_band=(0.2, 0.1))
             for _ in range(1000)]
    assert all(0.9 <= v <= 1.0 for v in above)
    assert all(0.0 <= v <= 0.2 for v in below)
    assert len(set(above)) == 1000 and len(set(below)) == 1000


def test_an_unbounded_side_needs_a_band_or_a_fallback():
    with pytest.raises(ValueError):
        sample_within(lambda: -1.0, 0.0, float("inf"), max_tries=1)
    assert 5.0 <= sample_within(lambda: 1.0, 5.0, float("inf"), max_tries=1, edge_band=1.0) <= 6.0
    assert sample_within(lambda: 1.0, 5.0, float("inf"), max_tries=1, fallback=lambda: 7.0) == 7.0


def test_empty_bounds_are_an_error():
    with pytest.raises(ValueError):
        sample_within(lambda: 0.0, 1.0, 0.0)


def test_a_seeded_stream_is_unchanged_when_the_bounds_do_not_bind():
    plain, bounded = random.Random(11), random.Random(11)
    expected = [plain.gauss(0.0, 1.0) for _ in range(50)]
    got = [sample_within(lambda: bounded.gauss(0.0, 1.0), -100.0, 100.0) for _ in range(50)]
    assert got == expected


@pytest.mark.parametrize("mean, cv, lo, hi", [
    (0.55, 0.34, 0.24, 0.96),
    (10.0, 0.5, 3.0, 60.0),
    (11.5, 0.35, 4.0, 28.0),
    (1.0, 0.18, 0.6, 1.6),
])
def test_lognormal_keeps_its_mean_once_truncated(mean, cv, lo, hi):
    rng = random.Random(21)
    values = [lognormal_with_mean(mean, cv, lo, hi, rng=rng) for _ in range(100_000)]
    assert all(lo <= v <= hi for v in values)
    assert abs(statistics.fmean(values) - mean) < 0.01 * mean
    assert statistics.median(values) < statistics.fmean(values)     # right-skewed


def test_lognormal_without_spread_is_the_mean():
    assert lognormal_with_mean(3.0, 0.0, 1.0, 5.0) == 3.0


def test_lognormal_refuses_a_mean_outside_its_bounds():
    with pytest.raises(ValueError):
        lognormal_with_mean(10.0, 0.3, 11.0, 20.0)
