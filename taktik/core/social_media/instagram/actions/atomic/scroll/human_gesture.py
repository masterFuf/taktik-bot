"""Human gesture engine: replay real human swipe trajectories instead of straight,
fixed, centred swipes (which are trivially fingerprintable).

The calibration (`human_scroll_calibration.json`, generated from days of recorded human
Instagram sessions) holds normalised real swipes. We bootstrap-sample a real tuple, add
small noise, denormalise onto the target screen, then build a slightly curved multi-point
path with an ease-in/out velocity profile and execute it via uiautomator2 `swipe_points`.

Key facts learned from the real data (n=260 forward swipes), all reproduced here by
sampling rather than hard-coding:
  - scroll distance ≈ 17% of screen height median (NOT the old fixed 40%);
  - the thumb starts right-of-centre (~0.61 width), never dead-centre, widely spread;
  - real horizontal drift ≈ 5% width median (up to 15%) — swipes are diagonal, not vertical;
  - duration ≈ 270ms median, broad.
"""

from __future__ import annotations

import json
import math
import os
import random
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

_CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), "human_scroll_calibration.json")


@lru_cache(maxsize=1)
def load_calibration() -> Dict:
    """Load (and cache) the human-scroll calibration. Returns a minimal safe default if
    the file is missing/corrupt so the caller never crashes a workflow over telemetry."""
    try:
        with open(_CALIBRATION_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("up"):
            return data
    except (OSError, ValueError):
        pass
    # Fallback mirrors the real medians so behaviour stays plausible without the dataset.
    return {
        "up": [{"nx": 0.61, "ny": 0.69, "ndy": -0.173, "ndx": 0.05, "dur": 300}],
        "down": [{"nx": 0.6, "ny": 0.49, "ndy": 0.18, "ndx": 0.04, "dur": 240}],
        "dwell_ms": [13000],
        "idle_ms": [9000],
        "read_pause_ms": [4000, 6000, 13000],
        "burst_gap_ms": [800, 1180, 1600],
    }


def _ease(t: float) -> float:
    """Gentle ease-in/out (smoothstep blended halfway with linear). Keeps some acceleration
    and deceleration like a real flick, but moves promptly at the start instead of dwelling
    near the touch-down point — a long initial dwell can be read as a tap (and would open an
    inline feed reel)."""
    return 0.5 * (t * t * (3.0 - 2.0 * t)) + 0.5 * t


def _bezier_path(
    sx: float, sy: float, ex: float, ey: float, *, points: int, curve_px: float
) -> List[List[int]]:
    """Quadratic-bezier path from start to end with a perpendicular mid control offset,
    sampled at eased parameter values so the velocity is non-uniform (human)."""
    mx, my = (sx + ex) / 2.0, (sy + ey) / 2.0
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy) or 1.0
    # Unit perpendicular to the swipe direction → bows the path sideways slightly.
    perp_x, perp_y = -dy / length, dx / length
    cx, cy = mx + perp_x * curve_px, my + perp_y * curve_px

    path: List[List[int]] = []
    for i in range(points + 1):
        t = _ease(i / points)
        omt = 1.0 - t
        x = omt * omt * sx + 2 * omt * t * cx + t * t * ex
        y = omt * omt * sy + 2 * omt * t * cy + t * t * ey
        path.append([int(round(x)), int(round(y))])
    return path


def sample_swipe(
    screen_w: int,
    screen_h: int,
    *,
    direction: str = "up",
    distance_px: Optional[float] = None,
    start_band: Optional[Tuple[float, float]] = None,
    dist_floor_h: float = 0.09,
    dist_cap_h: float = 0.34,
    rng: Optional[random.Random] = None,
) -> Tuple[List[List[int]], float]:
    """Build a human swipe for the target screen.

    Args:
        direction: 'up' = feed forward (content moves up), 'down' = back up.
        distance_px: optional vertical distance override (used by the intelligent feed
            scroll to land a post precisely). The *style* (start point, drift, duration,
            curvature) is still sampled from real data; only the magnitude is overridden,
            scaled within human bounds. When None the real sampled distance is used.
        start_band: optional (min_y, max_y) in pixels constraining the gesture's start Y.
            The feed scroll uses it to start the swipe OUTSIDE a dominant inline-reel/video
            element — a swipe contained within a feed reel is read by Instagram as "open the
            reel", not "scroll the feed".
        dist_floor_h / dist_cap_h: clamp band for the vertical magnitude as a fraction of
            screen height. Defaults (0.09 / 0.34) match the real flick envelope. The strong
            flick widens the cap (~0.45) and the long continuous drag widens it a lot (~0.95)
            so a deliberate "drag the post into view" can travel most of a screen.

    Returns (path_points, duration_seconds) ready for `swipe_points`.
    """
    rng = rng or random
    cal = load_calibration()
    pool = cal.get(direction) or cal.get("up") or []
    base = rng.choice(pool)

    sign = -1.0 if direction == "up" else 1.0
    # Start point: real normalised position + tiny jitter, clamped to safe margins.
    sx = base["nx"] * screen_w + rng.uniform(-0.015, 0.015) * screen_w
    sx = min(max(sx, 0.06 * screen_w), 0.94 * screen_w)
    if start_band is not None:
        lo, hi = min(start_band), max(start_band)
        sy = rng.uniform(lo, hi)
    else:
        sy = base["ny"] * screen_h + rng.uniform(-0.02, 0.02) * screen_h
    # Upper bound 0.85h: a gesture must NEVER start on the bottom navigation bar (~bottom 11% of
    # the screen, tab bar top ≈ 0.886h). A touch-down on it — e.g. the Search/Explore tab — opens
    # that tab (and its keyboard) instead of scrolling. 0.85h keeps the start on the media/content,
    # clear of the nav, on every device (ratio-based). The real human start tops out ~0.83h anyway.
    sy = min(max(sy, 0.10 * screen_h), 0.85 * screen_h)

    # Vertical magnitude: sampled, or overridden, then kept within the real human envelope.
    # Floor at ~9% screen height so a gesture always flings the feed and is never read as a
    # tap (a short tap on an inline feed reel opens the full Reels viewer).
    sampled_dy = abs(base["ndy"]) * screen_h
    if distance_px is not None:
        dy_mag = min(max(abs(distance_px), dist_floor_h * screen_h), dist_cap_h * screen_h)
    else:
        dy_mag = max(sampled_dy, dist_floor_h * screen_h)
    dy = sign * dy_mag
    ey = min(max(sy + dy, 0.04 * screen_h), 0.96 * screen_h)
    actual_dy = abs(ey - sy)   # vertical room may clamp near the edges

    # Horizontal drift: keep the real drift-to-distance proportion, but HARD-CAP it to 15% of
    # the actual vertical travel so the gesture stays clearly vertical (≤ ~8.5° off axis). A
    # too-diagonal swipe on the feed is read as a horizontal swipe — swipe-right opens the
    # story camera (and its gallery-permission modal). A little drift stays for realism; a
    # near-diagonal never happens.
    drift_ratio = base["ndx"] / (abs(base["ndy"]) or 0.17)
    dx = drift_ratio * actual_dy + rng.uniform(-0.01, 0.01) * screen_w
    max_dx = 0.15 * actual_dy
    dx = max(-max_dx, min(max_dx, dx))

    ex = min(max(sx + dx, 0.04 * screen_w), 0.96 * screen_w)

    # Duration: scale the real duration by how much we stretched the distance, + jitter.
    # Capped at 0.85s total so the gesture stays a flick that flings the feed, not a slow
    # drag (real cleaned swipes were ≤ ~0.85s at p90).
    scale = (dy_mag / sampled_dy) if sampled_dy > 1 else 1.0
    duration_ms = base["dur"] * min(max(scale, 0.7), 1.4) * rng.uniform(0.9, 1.12)
    duration_ms = min(max(duration_ms, 90.0), 850.0)

    # Very slight sideways bow on top of the end-point drift (random side). Kept small —
    # it is perpendicular (horizontal) to a vertical swipe, so a large bow would re-introduce
    # the horizontal-swipe ambiguity the dx cap just removed.
    seg_len = math.hypot(ex - sx, ey - sy) or 1.0
    curve_px = rng.uniform(0.004, 0.015) * seg_len * rng.choice((-1.0, 1.0))
    # Few points on purpose: the executor injects one input event per point over RPC, so a
    # high count makes every segment slow (no fling). With ~6 points each move is a big jump,
    # and a near-instant last move imparts real release velocity → the feed actually coasts.
    n_points = rng.randint(5, 7)

    path = _bezier_path(sx, sy, ex, ey, points=n_points, curve_px=curve_px)
    return path, duration_ms / 1000.0


def sample_reading_pause(rng: Optional[random.Random] = None) -> float:
    """A human reading pause between scroll bursts, in seconds. Bootstrapped from the real
    **inter-scroll gaps** (`read_pause_ms`, median ≈ 6.1s, long tail to ~25s+) — the right
    distribution for a feed-browsing rhythm. Falls back to SCREEN_CHANGE dwell (~13s) then a
    constant if the dataset lacks them. The long tail is essential: never a constant."""
    rng = rng or random
    cal = load_calibration()
    pool = cal.get("read_pause_ms") or cal.get("dwell_ms") or [6000]
    return rng.choice(pool) / 1000.0 * rng.uniform(0.9, 1.12)


def sample_burst_gap(rng: Optional[random.Random] = None) -> float:
    """The pause between two flicks of the SAME burst, in seconds (real inter-flick gaps,
    median ~1.18s, range ~0.6-2.4s). This length is essential for smoothness: it lets the
    previous fling's coast die before the next finger-down, so the next flick does not CATCH
    (abruptly stop) a still-coasting list — the catch is what reads as a robotic jolt."""
    rng = rng or random
    cal = load_calibration()
    pool = cal.get("burst_gap_ms") or [800, 1180, 1600]
    return rng.choice(pool) / 1000.0 * rng.uniform(0.9, 1.12)
