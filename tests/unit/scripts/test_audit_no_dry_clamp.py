"""The dry-clamp audit sees a random draw pushed onto its bound, and only that."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import audit_no_dry_clamp as audit  # noqa: E402


def _sources(source: str) -> list:
    return [finding.source for finding in audit.scan_source(source)]


@pytest.mark.parametrize("source, expected", [
    ("import random\nx = min(max(random.gauss(0, 1), -1), 1)",
     ["min(max(random.gauss(0, 1), -1), 1)"]),
    ("def f(rng, lo):\n    return max(lo, rng.uniform(0, 2))",
     ["max(lo, rng.uniform(0, 2))"]),
    ("def f(self):\n    x = self._rng.gauss(0, 1) * 3\n    y = x + 1\n    return min(y, 2.0)",
     ["min(y, 2.0)"]),
    ("import numpy as np\nv = np.clip(np.random.normal(0, 1), 0, 1)",
     ["np.clip(np.random.normal(0, 1), 0, 1)"]),
    ("def f():\n    ms = sample_tap_down_ms()\n    return max(ms, 40)",
     ["max(ms, 40)"]),
])
def test_a_clamped_draw_is_found(source, expected):
    assert _sources(source) == expected


@pytest.mark.parametrize("source", [
    # Clamps of parameters and of deterministic values are geometry, not draws.
    "def f(w, x):\n    return min(max(x, 0.05 * w), 0.95 * w)",
    # The count of a sampled path is not a draw.
    "def f(rng):\n    path = sample_swipe(rng=rng)\n    return max(1, len(path) - 1)",
    # Limits handed to the redraw primitive are limits.
    "def f(rng, sx, cap):\n"
    "    return sample_within(lambda: rng.gauss(0, 1), max(-cap, rng.random() - sx), cap)",
    # The redraw itself.
    "def f(rng):\n    return sample_within(lambda: rng.gauss(0, 1), -1, 1)",
])
def test_what_is_not_a_clamped_draw_is_left_alone(source):
    assert _sources(source) == []


def test_the_repository_has_no_dry_clamp_left_and_no_stale_exception():
    findings = audit.collect()
    keys = {finding.key for finding in findings}
    assert [f.render() for f in findings if f.key not in audit.ALLOWED] == []
    assert [key for key in audit.ALLOWED if key not in keys] == []
