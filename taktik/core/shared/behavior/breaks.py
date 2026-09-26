"""Break rhythm: after how many actions a pause comes, and how long it lasts.

Log-normal laws with a set mean, scaled by a tempo drawn once per session and truncated by
redrawing (`sampling.lognormal_with_mean`), so the spacing is neither a fixed period nor the same
narrow band in every session. Shared by the Instagram rhythm (`HumanBehavior`) and the TikTok
workflows.
"""

from __future__ import annotations

import math
from typing import Tuple

from taktik.core.shared.behavior.sampling import lognormal_with_mean

SPACING_CV = 0.35
LENGTH_CV = 0.5
# (mean, cv, min, max). Mean 1, so the long-run averages hold.
SESSION_TEMPO = (1.0, 0.18, 0.6, 1.6)
# Spacing bounds relative to its mean: 4 and 28 around the Instagram mean of 11.5.
SPACING_BOUNDS = (4.0 / 11.5, 28.0 / 11.5)


def session_tempo(*, rng=None) -> float:
    """One session's tempo: it breaks more often, or longer, than another."""
    mean, cv, lo, hi = SESSION_TEMPO
    return lognormal_with_mean(mean, cv, lo, hi, rng=rng)


def actions_until_break(mean: float, lo: float, hi: float, *, tempo: float = 1.0, rng=None) -> int:
    """Actions before the next break: a count around `mean x tempo`, within [lo, hi]."""
    return int(math.floor(lognormal_with_mean(mean * tempo, SPACING_CV, lo, hi, rng=rng) + 0.5))


def break_seconds(mean: float, lo: float, hi: float, *, tempo: float = 1.0, rng=None) -> float:
    """Length of a break in seconds, around `mean x tempo`, within [lo, hi]."""
    return lognormal_with_mean(mean * tempo, LENGTH_CV, lo, hi, rng=rng)


def spacing_bounds(every: float) -> Tuple[float, float]:
    """Spacing bounds for a configured mean `every` (>= 1). The lower one never rounds below 1."""
    low, high = SPACING_BOUNDS
    return max(0.5, every * low), every * high


__all__ = [
    "LENGTH_CV",
    "SESSION_TEMPO",
    "SPACING_BOUNDS",
    "SPACING_CV",
    "actions_until_break",
    "break_seconds",
    "session_tempo",
    "spacing_bounds",
]
