"""Shared like-method chooser — alternates double-tap vs button, ~DOUBLE_TAP_LIKE_PROB."""

import random

from taktik.core.shared.behavior.like_method import (
    DOUBLE_TAP_LIKE_PROB,
    should_double_tap_like,
)


def test_returns_bool():
    assert isinstance(should_double_tap_like(), bool)


def test_distribution_matches_prob():
    rng = random.Random(42)
    n = 5000
    frac = sum(should_double_tap_like(rng=rng) for _ in range(n)) / n
    assert abs(frac - DOUBLE_TAP_LIKE_PROB) < 0.03


def test_deterministic_with_seed():
    a = [should_double_tap_like(rng=random.Random(7)) for _ in range(10)]
    b = [should_double_tap_like(rng=random.Random(7)) for _ in range(10)]
    assert a == b


def test_both_methods_occur():
    rng = random.Random(1)
    outcomes = {should_double_tap_like(rng=rng) for _ in range(200)}
    assert outcomes == {True, False}  # neither method is ever exclusive
