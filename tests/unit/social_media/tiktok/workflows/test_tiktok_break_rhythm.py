"""TikTok breaks come after a drawn number of actions, around `pause_after_actions`.

The configured count is the mean spacing, with a tempo per session (`shared/behavior/breaks.py`).
The pause length stays in the configured range; strict regression runs keep the fixed period.
"""

import random
import statistics
import types

import pytest

from taktik.core.shared.behavior.session_state import BehaviorSessionState
from taktik.core.social_media.tiktok.actions.business.workflows._internal import base_workflow

EVERY = 10
SESSIONS = 1500
ACTIONS = 300
BREAKS_PER_SESSION = 30


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(base_workflow.time, "sleep", lambda _s: None)


def _workflow(state, every=EVERY):
    wf = object.__new__(base_workflow.BaseTikTokWorkflow)
    wf.config = types.SimpleNamespace(pause_after_actions=every,
                                      pause_duration_min=30.0, pause_duration_max=60.0)
    wf.behavior_state = state
    wf.logger = types.SimpleNamespace(info=lambda *_a: None, warning=lambda *_a: None)
    wf._actions_since_pause = 0
    wf._next_pause_after = None
    wf._on_pause_callback = None
    return wf


def _run(state, every=EVERY, actions=ACTIONS, breaks=None):
    """Action indices at which a break was taken, and the break lengths: over `actions` actions,
    or until `breaks` breaks were taken."""
    wf = _workflow(state, every)
    breaks_at, lengths = [], []
    wf._on_pause_callback = lambda seconds: lengths.append(seconds)
    for action in range(1, actions + 1):
        if breaks is not None and len(breaks_at) >= breaks:
            break
        wf._actions_since_pause += 1
        before = len(lengths)
        wf._check_pause_needed()
        if len(lengths) > before:
            breaks_at.append(action)
    return breaks_at, lengths


def _spacings(breaks_at):
    return [b - a for a, b in zip([0] + breaks_at, breaks_at)]


def _per_value_peak(values):
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


def test_breaks_are_not_a_period_and_keep_the_configured_mean():
    # As many breaks in every session: a fixed number of actions would under-count the sessions
    # whose tempo spaces their breaks out, and cut their last spacing.
    random.seed(11)
    spacings, session_means = [], []
    for session in range(SESSIONS):
        state = BehaviorSessionState(seed=session)
        own = _spacings(_run(state, actions=100_000, breaks=BREAKS_PER_SESSION)[0])
        assert len(own) == BREAKS_PER_SESSION
        spacings.extend(own)
        session_means.append(statistics.fmean(own))
    assert abs(statistics.fmean(spacings) - EVERY) < 0.15
    assert statistics.pstdev(spacings) > 3.0                 # was 0: every 10th action
    assert len(set(spacings)) > 10
    assert min(spacings) >= 1
    assert _per_value_peak(spacings) == 0.0
    # Each session has its own tempo: session means spread well beyond the sampling noise.
    noise = statistics.pstdev(spacings) / BREAKS_PER_SESSION ** 0.5
    assert statistics.pstdev(session_means) > 1.5 * noise


def test_a_break_still_lasts_within_the_configured_range():
    random.seed(12)
    lengths = []
    for session in range(200):
        lengths.extend(_run(BehaviorSessionState(seed=session))[1])
    assert lengths and all(30 <= s <= 60 for s in lengths)


def test_strict_regression_keeps_the_fixed_period():
    breaks_at, _ = _run(BehaviorSessionState(strict_regression=True))
    assert breaks_at == list(range(EVERY, ACTIONS + 1, EVERY))


@pytest.mark.parametrize("every", [0, -1])
def test_a_count_below_one_is_taken_as_given(every):
    breaks_at, _ = _run(BehaviorSessionState(), every=every, actions=5)
    assert breaks_at == [1, 2, 3, 4, 5]


def test_a_count_of_one_never_draws_zero():
    for session in range(500):
        spacings = _spacings(_run(BehaviorSessionState(seed=session), every=1, actions=50)[0])
        assert min(spacings) >= 1 and max(spacings) >= 1


def test_a_seeded_run_repeats_its_breaks_and_keeps_its_gesture_stream():
    first = _run(BehaviorSessionState(seed=5))[0]
    assert first == _run(BehaviorSessionState(seed=5))[0]
    assert first != _run(BehaviorSessionState(seed=6))[0]

    drew, untouched = BehaviorSessionState(seed=5), BehaviorSessionState(seed=5)
    _run(drew)
    assert drew._rng.random() == untouched._rng.random()


def test_without_a_behaviour_state_the_configured_count_is_used():
    breaks_at, _ = _run(None, actions=30)
    assert breaks_at == [10, 20, 30]
