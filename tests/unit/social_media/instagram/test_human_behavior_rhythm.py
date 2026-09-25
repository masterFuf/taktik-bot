"""Breaks and micro-delays are less regular, with the averages they always had.

Before: a short break every 8-15 interactions (uniform, sd 2.3), lasting 5-15 s (uniform), the
same narrow band in every session; micro-delays on a gaussian of sd = range / 4 clamped to
[0.8 min, 1.2 max]. Now: log-normal laws with the same means, wider, a per-session tempo, and
truncation by redrawing. There is no long break any more: it never fired (both kinds counted from
the last break of either kind, and the short one always came due first), and it was removed
rather than repaired.
"""

import random
import statistics
import time

import pytest

from taktik.core.social_media.instagram.actions.core.behavior import human_behavior as hb_module
from taktik.core.social_media.instagram.actions.core.behavior.human_behavior import HumanBehavior

SESSIONS = 3000
OLD_SPACING_SD = statistics.pstdev(range(8, 16))        # uniform 8..15
OLD_SHORT_BREAK_SD = 10.0 / (12 ** 0.5)                 # uniform 5..15 s


@pytest.fixture
def fresh_human(monkeypatch):
    monkeypatch.setattr(HumanBehavior, "_instance", None)

    def make():
        HumanBehavior._instance = None
        return HumanBehavior()

    return make


@pytest.fixture(autouse=True)
def _seeded():
    random.seed(4242)


def _per_value_peak(values):
    """Largest ratio of a value's count to the mean of its two neighbours' counts (the ends are
    compared with the next two inside). Only significant excesses count."""
    lo, hi = min(values), max(values)
    counts = [0] * (hi - lo + 1)
    for v in values:
        counts[v - lo] += 1
    worst = 0.0
    for i, c in enumerate(counts):
        nb = counts[1:3] if i == 0 else counts[-3:-1] if i == len(counts) - 1 else [counts[i - 1], counts[i + 1]]
        mean = sum(nb) / len(nb)
        if c > 1.5 * mean and c - 1.5 * mean > 4 * max(mean, 1.0) ** 0.5:
            worst = max(worst, c / max(mean, 1e-9))
    return worst


def test_break_spacing_keeps_its_mean_and_spreads_more(fresh_human):
    spacings, session_means = [], []
    for _ in range(SESSIONS):
        human = fresh_human()
        own = [human._break_every(hb_module._SHORT_BREAK_EVERY) for _ in range(40)]
        spacings.extend(own)
        session_means.append(statistics.fmean(own))
    assert abs(statistics.fmean(spacings) - 11.5) < 0.2
    assert statistics.pstdev(spacings) > 1.5 * OLD_SPACING_SD
    assert 4 <= min(spacings) and max(spacings) <= 28
    assert _per_value_peak(spacings) == 0.0
    # Sessions no longer share one rhythm: the old uniform gave a session mean sd of ~0.36 over
    # 40 breaks; the session tempo moves it by about two interactions.
    assert statistics.pstdev(session_means) > 3 * (OLD_SPACING_SD / 40 ** 0.5)


def test_short_break_length_keeps_its_mean_and_spreads_more(fresh_human):
    lengths = []
    for _ in range(SESSIONS):
        human = fresh_human()
        lengths.extend(human._break_length(hb_module._SHORT_BREAK_S) for _ in range(40))
    assert abs(statistics.fmean(lengths) - 10.0) < 0.2
    assert statistics.pstdev(lengths) > 1.5 * OLD_SHORT_BREAK_SD
    assert 3.0 <= min(lengths) and max(lengths) <= 60.0
    assert _per_value_peak([int(v) for v in lengths]) == 0.0


def test_breaks_still_come_from_the_real_interactions_only_and_are_short(fresh_human):
    kinds = []
    for _ in range(300):
        human = fresh_human()
        for _ in range(200):
            human.record_interaction()
            took, kind, duration = human.should_take_break()
            if took:
                kinds.append(kind)
                assert duration > 0
    assert kinds and set(kinds) == {"short"}


def test_no_long_break_even_when_the_short_one_is_far_away(fresh_human):
    """With the short break pushed out of reach, nothing else may pause the session."""
    for _ in range(300):
        human = fresh_human()
        human.interactions_before_short_break = 10_000
        for _ in range(200):
            human.record_interaction()
            assert human.should_take_break() == (False, None, 0)
    assert not hasattr(hb_module, "_LONG_BREAK_EVERY") and not hasattr(hb_module, "_LONG_BREAK_S")


def test_session_tempo_averages_one(fresh_human):
    tempos = [fresh_human().break_spacing_tempo for _ in range(SESSIONS)]
    assert abs(statistics.fmean(tempos) - 1.0) < 0.02
    assert 0.6 <= min(tempos) and max(tempos) <= 1.6


@pytest.mark.parametrize("low, high", [(0.3, 0.8), (0.15, 0.4), (0.08, 0.15), (1.2, 2.2)])
def test_micro_delay_keeps_the_range_middle_and_spreads_more(fresh_human, low, high):
    human = fresh_human()
    human.session_start = time.time()             # no fatigue on top of the draw
    values = [human.gaussian_delay(low, high) for _ in range(60_000)]
    mean = (low + high) / 2
    assert abs(statistics.fmean(values) - mean) < 0.01 * mean
    # The old gaussian had sd = range / 4 (a little less once clamped). The log-normal is drawn
    # half again as wide; the truncation to [0.8 min, 1.2 max] gives some of it back.
    assert statistics.pstdev(values) > 1.2 * (high - low) / 4
    assert min(values) >= 0.8 * low and max(values) <= 1.2 * high * 1.001
    assert statistics.median(values) < statistics.fmean(values)       # right-skewed


def test_micro_delay_of_an_empty_range_is_that_value(fresh_human):
    human = fresh_human()
    human.session_start = time.time()
    assert human.gaussian_delay(0.0, 0.0) == 0.0
    assert abs(human.gaussian_delay(0.4, 0.4) - 0.4) < 1e-3
