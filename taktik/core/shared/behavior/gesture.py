"""Swipe trajectory sampler.

A normalised calibration set is bootstrap-sampled, noised, denormalised onto the target
screen, then turned into a slightly curved multi-point path with an ease-in/out velocity
profile. Start point, distance, drift and duration all come from the sample rather than
from constants.
"""

from __future__ import annotations

import json
import math
import os
import random
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from loguru import logger

from taktik.core.shared.behavior.sampling import sample_within

_CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), "human_scroll_calibration.json")

# Screen envelope of a vertical swipe, as fractions of the screen height. The start stays clear of
# the status bar and of the bottom tab bars; the end stays on the glass.
_START_MIN_H, _START_MAX_H = 0.10, 0.85
_END_MIN_H, _END_MAX_H = 0.04, 0.96
# Longest travel the envelope permits (a down swipe from the highest start to the bottom edge; an
# up swipe gets 0.81). A larger `dist_cap_h` never lengthens a gesture.
FULL_REACH_H = round(_END_MAX_H - _START_MIN_H, 2)
# Share of the requested travel a swipe always covers when the request fits the room.
_FULL_TRAVEL_SHARE = 0.95


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


@lru_cache(maxsize=16)
def _swipe_pool(direction: str, min_ndy: float) -> tuple:
    """Calibrated swipes of `direction` whose vertical travel is at least `min_ndy` (fraction of
    the screen height); all of them when none is that long."""
    cal = load_calibration()
    pool = cal.get(direction) or cal.get("up") or []
    return tuple(item for item in pool if abs(item["ndy"]) >= min_ndy) or tuple(pool)


def _ease(t: float) -> float:
    """Gentle ease-in/out: smoothstep blended halfway with linear.

    Keeps acceleration and deceleration, but leaves the touch-down point promptly — dwelling
    there makes the gesture read as a tap."""
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


def travel_room(screen_h: int, direction: str,
                start_band: Optional[Tuple[float, float]] = None) -> float:
    """Longest vertical travel the envelope allows from the starts a gesture may use, in pixels.

    Up: from the highest allowed start down to the top edge. Down: from the lowest allowed start
    to the bottom edge. A `start_band` that overlaps the start envelope narrows it."""
    start_lo, start_hi = _start_interval(screen_h, start_band)
    if direction == "up":
        return start_hi - _END_MIN_H * screen_h
    return _END_MAX_H * screen_h - start_lo


def _start_interval(screen_h: int,
                    start_band: Optional[Tuple[float, float]]) -> Tuple[float, float]:
    lo, hi = _START_MIN_H * screen_h, _START_MAX_H * screen_h
    if start_band is None:
        return lo, hi
    band_lo, band_hi = min(start_band), max(start_band)
    if band_lo <= hi and band_hi >= lo:
        return max(lo, band_lo), min(hi, band_hi)
    # A band outside the envelope keeps its side: a strip of its width beside the nearest limit.
    width = min(max(band_hi - band_lo, 0.01 * screen_h), 0.04 * screen_h)
    return (hi - width, hi) if band_lo > hi else (lo, lo + width)


def _sampled_start_x(base, screen_w: int, rng) -> float:
    return sample_within(
        lambda: base["nx"] * screen_w + rng.uniform(-0.015, 0.015) * screen_w,
        0.06 * screen_w, 0.94 * screen_w, rng=rng, edge_band=0.03 * screen_w,
    )


def _sampled_travel_geometry(screen_w, screen_h, direction, start_band, dist_floor_h, rng):
    """Start, end and travel of a swipe that replays the travel of a real one."""
    floor_px = dist_floor_h * screen_h
    # Only swipes long enough to move the feed qualify, rather than lifting the short ones to
    # exactly the floor.
    pool = _swipe_pool(direction, dist_floor_h)
    base = rng.choice(pool)
    sign = -1.0 if direction == "up" else 1.0
    sx = _sampled_start_x(base, screen_w, rng)
    # The start must stay on the content, clear of the bottom navigation bar: a touch-down on
    # a tab opens it instead of scrolling. Ratio-based, so it holds on every device.
    start_lo, start_hi = _START_MIN_H * screen_h, _START_MAX_H * screen_h
    if start_band is not None:
        lo, hi = min(start_band), max(start_band)
        sy = sample_within(lambda: rng.uniform(lo, hi), start_lo, start_hi,
                           rng=rng, edge_band=max(hi - lo, 0.01 * screen_h))
    else:
        sy = sample_within(
            lambda: base["ny"] * screen_h + rng.uniform(-0.02, 0.02) * screen_h,
            start_lo, start_hi, rng=rng, edge_band=0.04 * screen_h,
        )
    sampled_dy = abs(base["ndy"]) * screen_h
    # The floor guarantees the gesture always moves the feed and is never read as a tap.
    dy_mag = sampled_dy if sampled_dy >= floor_px else floor_px + rng.uniform(0.0, 0.03) * screen_h
    # The end stays on the glass. When the travel asks for more room than there is, the finger
    # lifts somewhere within a finger-width of the edge, not on one fixed row.
    ey = sy + sign * dy_mag
    if not _END_MIN_H * screen_h <= ey <= _END_MAX_H * screen_h:
        edge = _END_MIN_H * screen_h if ey < _END_MIN_H * screen_h else _END_MAX_H * screen_h
        ey = edge + math.copysign(rng.uniform(0.0, 0.02) * screen_h, sy - edge)
    return sx, sy, ey, dy_mag, base, pool


def _requested_travel_geometry(screen_w, screen_h, direction, distance, start_band,
                               dist_floor_h, dist_cap_h, rng):
    """Start, end and travel of a swipe asked to cover `distance` pixels.

    The start is drawn among the REAL starts from which that travel fits on the glass: a start
    drawn first and a travel cut at the edge afterwards made a 0.7h request come out under 95 %
    of itself in 58 % of the gestures. A request longer than the room is bounded to the room and
    logged, with the travel asked and the travel obtained.
    """
    requested = max(distance, dist_floor_h * screen_h)
    room = travel_room(screen_h, direction, start_band)
    if requested > room:
        logger.debug(f"swipe travel bounded to the room: requested {round(requested)} px, "
                     f"room {round(room)} px ({direction})")
    target = min(requested, dist_cap_h * screen_h, room)
    # The finger may lift within a finger-width of the edge, never short of this share.
    need = _FULL_TRAVEL_SHARE * target
    start_lo, start_hi = _start_interval(screen_h, start_band)
    if direction == "up":
        start_lo = max(start_lo, _END_MIN_H * screen_h + need)
    else:
        start_hi = min(start_hi, _END_MAX_H * screen_h - need)

    pool = _swipe_pool(direction, 0.0)
    fitting = [item for item in pool if start_lo <= item["ny"] * screen_h <= start_hi]
    base = rng.choice(fitting or pool)
    sx = _sampled_start_x(base, screen_w, rng)
    strip = min(0.04 * screen_h, start_hi - start_lo)
    if start_band is not None:
        lo, hi = min(start_band), max(start_band)
        sy = sample_within(lambda: rng.uniform(lo, hi), start_lo, start_hi,
                           rng=rng, edge_band=strip)
    else:
        sy = sample_within(
            lambda: base["ny"] * screen_h + rng.uniform(-0.02, 0.02) * screen_h,
            start_lo, start_hi, rng=rng, edge_band=strip,
        )

    sign = -1.0 if direction == "up" else 1.0
    ey = sy + sign * target
    if not _END_MIN_H * screen_h <= ey <= _END_MAX_H * screen_h:
        edge = _END_MIN_H * screen_h if ey < _END_MIN_H * screen_h else _END_MAX_H * screen_h
        # The lift stays within a finger-width of the edge and never costs the travel its share.
        slack = abs(sy - edge) - need
        offset = (sample_within(lambda: rng.uniform(0.0, 0.02 * screen_h), 0.0, slack,
                                rng=rng, edge_band=slack)
                  if slack > 0 else 0.0)
        ey = edge + math.copysign(offset, sy - edge)
    return sx, sy, ey, target, base, pool


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
            flick widens the cap (0.45) and the controlled drags use `FULL_REACH_H`, the
            longest travel the envelope permits, so a deliberate "drag the post into view" can
            travel most of a screen.

    With `distance_px`, the travel covers at least 95 % of the request (after floor and cap)
    whenever the request fits the room `travel_room` gives; a longer request covers at least
    95 % of the room and is logged as bounded.

    Returns (path_points, duration_seconds) ready for `swipe_points`.

    Every sampled quantity that must stay inside a limit is drawn again when it falls outside,
    never pushed onto the limit: a limit hit by a share of the gestures would put that share on
    one exact value of the touch trace (start pixel, end row, drift angle, duration).
    """
    rng = rng or random
    if distance_px is not None:
        sx, sy, ey, dy_mag, base, pool = _requested_travel_geometry(
            screen_w, screen_h, direction, abs(distance_px), start_band,
            dist_floor_h, dist_cap_h, rng,
        )
    else:
        sx, sy, ey, dy_mag, base, pool = _sampled_travel_geometry(
            screen_w, screen_h, direction, start_band, dist_floor_h, rng,
        )
    actual_dy = abs(ey - sy)

    # Horizontal drift keeps a real sampled proportion but must stay under 0.15 of the vertical
    # travel, so the gesture is clearly vertical and never read as a sideways swipe. Most real
    # swipes drift more than that; capping them put four gestures in five on the same angle.
    # A drift over the limit is replaced by the drift of another real swipe, and the end point
    # is kept on the glass the same way.
    max_dx = 0.15 * actual_dy

    def drift_of(item) -> float:
        return item["ndx"] / (abs(item["ndy"]) or 0.17)

    dx = sample_within(
        lambda: drift_of(rng.choice(pool)) * actual_dy + rng.uniform(-0.01, 0.01) * screen_w,
        max(-max_dx, 0.04 * screen_w - sx), min(max_dx, 0.96 * screen_w - sx),
        rng=rng, first=drift_of(base) * actual_dy + rng.uniform(-0.01, 0.01) * screen_w,
    )
    ex = sx + dx

    # Duration: scale the real duration by how much we stretched the distance, + jitter.
    # Kept under 0.85s so the gesture stays a flick that flings the feed, not a slow
    # drag (real cleaned swipes were ≤ ~0.85s at p90). A duration outside 90-850 ms is replaced
    # by the duration of another real swipe stretched to the same distance.
    def stretched_ms(item) -> float:
        own_dy = abs(item["ndy"]) * screen_h
        scale = (dy_mag / own_dy) if own_dy > 1 else 1.0
        return item["dur"] * min(max(scale, 0.7), 1.4)

    duration_ms = sample_within(
        lambda: stretched_ms(rng.choice(pool)) * rng.uniform(0.9, 1.12), 90.0, 850.0,
        rng=rng, first=stretched_ms(base) * rng.uniform(0.9, 1.12), edge_band=(20.0, 150.0),
    )

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
    """Reading pause between scroll bursts, in seconds.

    Bootstrapped from the calibrated inter-scroll gaps, falling back to the dwell figures and
    then to a constant when the dataset lacks them. The long tail of the distribution is the
    point: this is never a constant."""
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
