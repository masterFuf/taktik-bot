"""Bounded random draws: a value outside its bounds is drawn again, never clamped.

`min(max(x, lo), hi)` on a random `x` turns every out-of-range draw into exactly `lo` or `hi`: the
distribution grows a spike on its edge -- taps glued to the rim of their target, durations worth
exactly the minimum -- that a touch heatmap or a timing histogram shows at a glance. Here the value
is drawn again; after a bounded number of misses it comes from a uniform draw inside the bounds, so
no call can loop and no value lands on a bound more often than its neighbours.

`lognormal_with_mean` builds on it for pauses: right-skewed like human delays, and with a mean that
stays exactly the configured one once truncated to its bounds.

`scripts/audit_no_dry_clamp.py` keeps new clamps of random draws out of the code.
"""

from __future__ import annotations

import math
import random
from functools import lru_cache
from typing import Callable, Optional, Tuple, Union

DEFAULT_MAX_TRIES = 32

EdgeBand = Union[float, Tuple[float, float]]


def sample_within(
    draw: Callable[[], float],
    lo: float,
    hi: float,
    *,
    rng=None,
    max_tries: int = DEFAULT_MAX_TRIES,
    first: Optional[float] = None,
    edge_band: Optional[EdgeBand] = None,
    fallback: Optional[Callable[[], float]] = None,
) -> float:
    """Return a value of `draw()` that lies in [lo, hi], drawing again when it does not.

    `first` is a value the caller already drew, tested before any new draw: it keeps the order of
    the caller's other draws, so a seeded run is unchanged whenever the bounds do not bind.

    After `max_tries` misses the value comes from `fallback()` when given, otherwise from a uniform
    draw: over [lo, hi], or -- with `edge_band` -- over that width (one width, or a (below, above)
    pair, in the value's own units) next to the bound the draws kept missing. The band keeps the
    side the caller's distribution was pushing towards without piling everything on one value.
    """
    if lo > hi:
        raise ValueError(f"empty bounds [{lo}, {hi}]")
    below = above = 0
    pending = [] if first is None else [first]
    for _ in range(max_tries + len(pending)):
        value = pending.pop() if pending else draw()
        if lo <= value <= hi:
            return value
        if value < lo:
            below += 1
        elif value > hi:
            above += 1

    if fallback is not None:
        return fallback()
    r = rng or random
    if edge_band is not None and below != above:
        width_below, width_above = (
            edge_band if isinstance(edge_band, tuple) else (edge_band, edge_band)
        )
        if below > above:
            return lo + r.uniform(0.0, min(float(width_below), hi - lo))
        return hi - r.uniform(0.0, min(float(width_above), hi - lo))
    if math.isinf(lo) or math.isinf(hi):
        raise ValueError("an unbounded side needs an edge_band or a fallback")
    return r.uniform(lo, hi)


def _phi_diff(z_lo: float, z_hi: float) -> float:
    """P(z_lo < Z < z_hi) for a standard normal, accurate in both tails."""
    if z_lo >= 0.0:
        return 0.5 * (math.erfc(z_lo / math.sqrt(2.0)) - math.erfc(z_hi / math.sqrt(2.0)))
    return 0.5 * (math.erfc(-z_hi / math.sqrt(2.0)) - math.erfc(-z_lo / math.sqrt(2.0)))


def _truncated_lognormal_mean(mu: float, sigma: float, lo: float, hi: float) -> float:
    log_lo = math.log(lo) if lo > 0.0 else -math.inf
    log_hi = math.log(hi) if math.isfinite(hi) else math.inf
    mass = _phi_diff((log_lo - mu) / sigma, (log_hi - mu) / sigma)
    if mass <= 1e-300:
        # All the mass sits beyond one bound: the truncated mean is that bound.
        return hi if mu > log_hi else lo
    shifted = _phi_diff((log_lo - mu - sigma * sigma) / sigma, (log_hi - mu - sigma * sigma) / sigma)
    return math.exp(mu + 0.5 * sigma * sigma) * shifted / mass


@lru_cache(maxsize=256)
def _unit_mean_mu(lo: float, hi: float, sigma: float) -> float:
    """The log-location giving a mean of exactly 1 once truncated to [lo, hi] (with lo < 1 < hi)."""
    low, high = -0.5 * sigma * sigma - 10.0 * sigma - 5.0, -0.5 * sigma * sigma + 10.0 * sigma + 5.0
    for _ in range(80):
        middle = 0.5 * (low + high)
        if _truncated_lognormal_mean(middle, sigma, lo, hi) < 1.0:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


def lognormal_with_mean(
    mean: float,
    cv: float,
    lo: float,
    hi: float,
    *,
    rng=None,
    max_tries: int = DEFAULT_MAX_TRIES,
) -> float:
    """A log-normal draw in [lo, hi] whose mean, AFTER truncation, is exactly `mean`.

    `cv` is the coefficient of variation of the untruncated law (standard deviation / mean). Human
    delays are right-skewed: most are close to typical, a few are much longer, none is negative.
    The truncation is done by redrawing (`sample_within`), and the log-location is solved so the
    bounds do not drag the average away from the configured value.
    """
    if cv <= 0.0 or mean <= 0.0:
        return mean
    if not lo < mean < hi:
        raise ValueError(f"mean {mean} outside ({lo}, {hi})")
    r = rng or random
    sigma = math.sqrt(math.log1p(cv * cv))
    unit_lo = round(max(0.0, lo) / mean, 9)
    unit_hi = round(hi / mean, 9) if math.isfinite(hi) else math.inf
    mu = _unit_mean_mu(unit_lo, unit_hi, round(sigma, 9)) + math.log(mean)
    return sample_within(lambda: r.lognormvariate(mu, sigma), lo, hi, rng=r, max_tries=max_tries)


__all__ = ["DEFAULT_MAX_TRIES", "lognormal_with_mean", "sample_within"]
