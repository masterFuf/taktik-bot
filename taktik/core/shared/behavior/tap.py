"""Human tap sampling: where to touch inside a target, and for how long.

A robotic tap hits the exact same pixel every time (the element centre, or a fixed
coordinate) with an instant press — trivially fingerprintable on a touch heatmap. A
human hits *near* the middle, never the dead centre twice, with a short but varied
finger-down time.

This is the geometry half of the "humanise taps" workstream
(`taktik-docs/bot/security/humanization-master-plan.md`). Pure functions, no device —
the device execution lives in `taktik/core/shared/device/facade.py::human_tap`.
"""

from __future__ import annotations

import random
from typing import Optional, Tuple

Bounds = Tuple[int, int, int, int]  # (left, top, right, bottom)

# Tap point spread (fraction of the half-size): people cluster around the centre.
_SPREAD = 0.38
# Inner margin (fraction of the size) kept off each edge, so we never hit the rim,
# the padding, or a neighbouring tappable.
_MARGIN = 0.12


def sample_tap_point(bounds: Bounds, *, rng: Optional[random.Random] = None) -> Tuple[int, int]:
    """Sample a human tap point inside `bounds` (left, top, right, bottom).

    Gaussian-weighted toward the centre, clamped to an inner margin so the tap stays
    well inside the element (never the rim) — and never the dead centre twice. For a
    tiny element this collapses toward the centre (as a human would, on a small target).
    """
    rng = rng or random
    lx, ty, rx, by = bounds
    # Tolerate inverted/degenerate boxes.
    left, right = (lx, rx) if lx <= rx else (rx, lx)
    top, bottom = (ty, by) if ty <= by else (by, ty)
    w = right - left
    h = bottom - top

    cx = left + w / 2.0
    cy = top + h / 2.0
    if w <= 1 and h <= 1:
        return int(round(cx)), int(round(cy))

    x = cx + rng.gauss(0.0, (w / 2.0) * _SPREAD)
    y = cy + rng.gauss(0.0, (h / 2.0) * _SPREAD)

    # Keep strictly inside: inner margin, but at least ~1px off each edge for real boxes.
    mx = max(min(w * _MARGIN, (w - 1) / 2.0), 0.0)
    my = max(min(h * _MARGIN, (h - 1) / 2.0), 0.0)
    x = min(max(x, left + mx), right - mx)
    y = min(max(y, top + my), bottom - my)
    return int(round(x)), int(round(y))


def sample_tap_down_ms(*, rng: Optional[random.Random] = None) -> float:
    """Human finger-down time for a tap, in milliseconds.

    Mostly quick (~70ms), occasionally a touch longer (a deliberate press), always well
    under the Android long-press threshold (~400-500ms) so it stays a tap, never a
    long-press. Varying the press time alone makes the touch trace less mechanical.
    """
    rng = rng or random
    ms = rng.gauss(70.0, 22.0)
    if rng.random() < 0.10:
        ms += rng.uniform(40.0, 110.0)  # occasional deliberate, slightly longer press
    return float(min(max(ms, 30.0), 220.0))
