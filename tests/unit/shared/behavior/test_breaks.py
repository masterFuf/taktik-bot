"""The shared break law holds for any configured spacing, not only the Instagram one."""

import random
import statistics

import pytest

from taktik.core.shared.behavior import breaks


@pytest.mark.parametrize("every", [1, 2, 3, 5, 10, 11.5, 25, 60, 100])
def test_a_configured_spacing_keeps_its_mean_and_never_rounds_below_one(every):
    rng = random.Random(7)
    lo, hi = breaks.spacing_bounds(every)
    tempo_lo, tempo_hi = breaks.SESSION_TEMPO[2:]
    # Every session tempo keeps the mean strictly inside the bounds the law needs.
    assert lo < every * tempo_lo and every * tempo_hi < hi
    values = [breaks.actions_until_break(every, lo, hi, rng=rng) for _ in range(40_000)]
    assert min(values) >= 1
    assert max(values) <= int(hi + 0.5)
    assert abs(statistics.fmean(values) - every) < 0.03 * every + 0.05


def test_the_instagram_bounds_are_the_shared_ratios():
    assert breaks.spacing_bounds(11.5) == pytest.approx((4.0, 28.0))


def test_a_session_tempo_averages_one_within_its_bounds():
    rng = random.Random(8)
    tempos = [breaks.session_tempo(rng=rng) for _ in range(40_000)]
    assert abs(statistics.fmean(tempos) - 1.0) < 0.01
    assert breaks.SESSION_TEMPO[2] <= min(tempos) and max(tempos) <= breaks.SESSION_TEMPO[3]
