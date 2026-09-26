"""No random draw of the humanisation piles up on its bounds.

`min(max(draw, lo), hi)` put a share of every distribution on exactly `lo` or `hi`: 4.6 % of the
taps on the two rim pixels of their zone, 88 % of the long drags at exactly 0.85 s, every long
drag lifted on the same row, four swipes in five on the same drift angle. The draws are now
redrawn (`sampling.sample_within`). Each primitive that used to clamp is drawn 400 000 times in
its usual regime; the values must stay inside their bounds and the 40-column histogram must show
no column over 1.5 times the mean of its two neighbours (an edge column is compared with the next
two inside). The limit regimes -- inputs for which no draw can fit and the value comes from the
strip beside the limit -- are drawn 100 000 times: they are plain uniform strips, and each of
their draws first spends the full budget of redraws.

`TAKTIK_DISTRIBUTION_DRAWS` lowers the count for a quick local run.
"""

import math
import os
import random
import time
import types
from collections import Counter

import pytest

import taktik.core.shared.behavior.gesture_primitives as gp
from taktik.core.shared.behavior import dwell
from taktik.core.shared.behavior.gesture import sample_swipe
from taktik.core.shared.behavior.tap import MAX_TAP_HOLD_MS, sample_tap_down_ms, sample_tap_point

DRAWS = int(os.environ.get("TAKTIK_DISTRIBUTION_DRAWS", "400000"))
LIMIT_DRAWS = DRAWS // 4
COLUMNS = 40
PEAK_RATIO = 1.5


def _columns(values):
    """Counts per column: one column per value when the values sit on a grid (rounded ratios,
    pixels, offsets), 40 equal columns over the observed range otherwise."""
    distinct = sorted(set(values))
    if len(distinct) <= 3 * COLUMNS:
        counts = Counter(values)
        return [counts[v] for v in distinct]
    low, high = distinct[0], distinct[-1]
    width = (high - low) / COLUMNS
    counts = Counter(min(COLUMNS - 1, int((v - low) / width)) for v in values)
    return [counts[i] for i in range(COLUMNS)]


def _worst_peak(values):
    columns = _columns(values)
    if len(columns) < 3:
        return math.inf                       # one or two values: a constant, the worst peak
    worst = 0.0
    for i, count in enumerate(columns):
        if i == 0:
            neighbours = columns[1:3]
        elif i == len(columns) - 1:
            neighbours = columns[-3:-1]
        else:
            neighbours = [columns[i - 1], columns[i + 1]]
        mean = sum(neighbours) / len(neighbours)
        # A peak must also be significant: a thin tail can double by chance.
        if count > PEAK_RATIO * mean and count - PEAK_RATIO * mean > 4.0 * math.sqrt(max(mean, 1.0)):
            worst = max(worst, count / max(mean, 1e-9))
    return worst


def _assert_bounded_without_peak(values, lo, hi, tolerance=1e-9):
    assert min(values) >= lo - tolerance, (min(values), lo)
    assert max(values) <= hi + tolerance, (max(values), hi)
    assert _worst_peak(values) == 0.0, _columns(values)


@pytest.fixture(autouse=True)
def _seeded():
    random.seed(20260925)


# --- taps ------------------------------------------------------------------------------------

def test_tap_point_is_not_glued_to_the_rim_of_its_zone():
    rng = random.Random(1)
    points = [sample_tap_point((100, 500, 500, 700), rng=rng) for _ in range(DRAWS)]
    _assert_bounded_without_peak([x for x, _ in points], 148, 452)
    _assert_bounded_without_peak([y for _, y in points], 524, 676)


def test_tap_press_time_never_sticks_to_its_minimum_nor_to_its_cap():
    rng = random.Random(2)
    values = [sample_tap_down_ms(rng=rng) for _ in range(DRAWS)]
    _assert_bounded_without_peak(values, 30.0, MAX_TAP_HOLD_MS)


# --- TikTok facade -----------------------------------------------------------------------------

def test_tiktok_coordinate_jitter_has_no_rim_nor_centre_spike():
    from taktik.core.social_media.tiktok.actions.core.device_facade import DeviceFacade

    offsets = [DeviceFacade._jitter_point(500, 900) for _ in range(DRAWS)]
    _assert_bounded_without_peak([x - 500 for x, _ in offsets], -8, 8)
    _assert_bounded_without_peak([y - 900 for _, y in offsets], -8, 8)


@pytest.mark.parametrize("scale, draws", [(0.8, DRAWS), (0.4, LIMIT_DRAWS), (1.0, LIMIT_DRAWS)])
def test_tiktok_list_scroll_ratio_is_never_a_constant(scale, draws):
    from taktik.core.social_media.tiktok.actions.core.device_facade import DeviceFacade

    values = [DeviceFacade._list_scroll_ratio(scale) for _ in range(draws)]
    _assert_bounded_without_peak(values, 0.18, 0.34)


@pytest.mark.parametrize("distance_scale", [0.95, 1.1])
def test_tiktok_pager_drag_does_not_pile_on_its_floor(distance_scale):
    from taktik.core.social_media.tiktok.actions.core.device_facade import DeviceFacade

    values = [DeviceFacade._pager_drag_ratio(distance_scale) for _ in range(DRAWS)]
    _assert_bounded_without_peak(values, 0.56, 0.85)


# --- swipe sampler ----------------------------------------------------------------------------

def test_sampled_swipe_drift_duration_and_travel_have_no_spike():
    rng = random.Random(3)
    w, h = 1080, 2400
    drift, duration, start_x, travel = [], [], [], []
    for _ in range(DRAWS):
        path, seconds = sample_swipe(w, h, direction="up", rng=rng)
        (x0, y0), (x1, y1) = path[0], path[-1]
        dy = abs(y1 - y0)
        # Points are rounded to pixels: allow one pixel of slack on the drift cap.
        drift.append((x1 - x0) / dy)
        assert abs(x1 - x0) <= 0.15 * dy + 1.5
        duration.append(seconds * 1000.0)
        start_x.append(x0)
        travel.append(dy)
    _assert_bounded_without_peak(drift, -0.16, 0.16)
    _assert_bounded_without_peak(duration, 90.0, 850.0)
    # Start and travel replay a finite set of real swipes, so their histograms are lumpy by
    # nature; what must be gone is the share lifted onto the limits (was 13.5 % on the floor).
    assert min(start_x) >= round(0.06 * w) and max(start_x) <= round(0.94 * w)
    assert start_x.count(round(0.94 * w)) / DRAWS < 0.002
    assert min(travel) >= round(0.09 * h) - 1
    assert travel.count(round(0.09 * h)) / DRAWS < 0.01


def test_long_drag_end_row_is_not_one_row():
    rng = random.Random(4)
    w, h = 1080, 2400
    ends = [
        sample_swipe(w, h, direction="up", distance_px=0.84 * h, start_band=(0.78 * h, 0.85 * h),
                     dist_cap_h=0.95, rng=rng)[0][-1][1]
        for _ in range(LIMIT_DRAWS)
    ]
    _assert_bounded_without_peak(ends, round(0.04 * h), round(0.06 * h))


# --- gesture durations ------------------------------------------------------------------------

@pytest.mark.parametrize("dy, draws", [(600, DRAWS), (150, LIMIT_DRAWS)])
def test_fling_total_duration(dy, draws):
    _assert_bounded_without_peak([gp._fling_total_duration(dy) for _ in range(draws)], 0.06, 0.24)


@pytest.mark.parametrize("dy, draws", [(1200, DRAWS), (400, LIMIT_DRAWS)])
def test_flick_duration(dy, draws):
    values = [gp._flick_duration(dy, (9000.0, 13000.0)) for _ in range(draws)]
    _assert_bounded_without_peak(values, 0.045, 0.11)


@pytest.mark.parametrize("dy, draws", [(1500, DRAWS), (2400, LIMIT_DRAWS)])
def test_long_drag_duration(dy, draws):
    values = [gp._drag_duration(dy, (1500.0, 2200.0)) for _ in range(draws)]
    _assert_bounded_without_peak(values, 0.40, 0.85)


def test_controlled_drag_velocity_is_not_parked_on_the_band_edge():
    rng = random.Random(5)
    travel = 0.62 * 2400
    low, high = gp._CONTROLLED_VEL_RANGE
    velocities = [
        travel / gp._controlled_duration(rng.uniform(0.1, 0.9), travel,
                                         redraw=lambda: rng.uniform(0.1, 0.9))
        for _ in range(DRAWS)
    ]
    _assert_bounded_without_peak(velocities, low, high, tolerance=1e-6)


class _Raw:
    def __init__(self):
        self.calls = []

    def swipe(self, x1, y1, x2, y2, duration=0.5):
        self.calls.append((x1, y1, x2, y2, duration))


def test_horizontal_swipe_end_and_duration(monkeypatch):
    monkeypatch.setattr(gp, "emit_step", lambda *_a, **_k: None)
    monkeypatch.setattr(gp.time, "sleep", lambda _s: None)
    raw = _Raw()
    host = gp._RawGestureHost()
    host.device = types.SimpleNamespace(_device=raw)
    host.logger = types.SimpleNamespace(error=lambda *_a: None, debug=lambda *_a: None)
    host.screen_width, host.screen_height = 1080, 2400
    for _ in range(DRAWS):
        host._human_horizontal_swipe("left", 0.6, velocity_scale=1.45, distance_scale=1.2)
    _assert_bounded_without_peak([c[4] for c in raw.calls], 0.16, 0.50)
    _assert_bounded_without_peak([c[2] for c in raw.calls], int(0.05 * 1080), int(0.95 * 1080) + 1)


# --- dwell and delays -------------------------------------------------------------------------

@pytest.mark.parametrize("prose_len, draws", [(300, DRAWS), (700, LIMIT_DRAWS)])
def test_reading_dwell_is_not_the_cap(prose_len, draws):
    values = [dwell.content_dwell(prose_len) for _ in range(draws)]
    most = dwell.GLANCE_S[1] + dwell.READ_CAP_S + dwell.LINGER_S[1]
    _assert_bounded_without_peak(values, dwell.GLANCE_S[0], most)


def test_shared_human_like_delay():
    from taktik.core.shared.actions.utils import ActionUtils

    values = [ActionUtils.generate_human_like_delay(0.5, 1.0) for _ in range(DRAWS)]
    _assert_bounded_without_peak(values, 0.5, 1.0)


@pytest.mark.parametrize("chars, draws", [(120, DRAWS), (400, LIMIT_DRAWS)])
def test_dm_typing_delay_is_not_five_seconds_flat(chars, draws):
    from taktik.core.shared.behavior.typing import calculate_dm_typing_delay

    values = [calculate_dm_typing_delay("x" * chars) for _ in range(draws)]
    _assert_bounded_without_peak(values, 0.0, 5.0)


@pytest.mark.parametrize("profile, floor, lo, hi, draws", [
    ("natural", 5.0, 5.0, 6.0, LIMIT_DRAWS),    # the whole 0-1 s range sits under the floor
    ("balanced", 8.0, 8.0, 15.0, DRAWS),        # part of 5-15 s does: redrawn, not raised
])
def test_warmup_floor_is_not_a_metronome(profile, floor, lo, hi, draws):
    from taktik.core.social_media.instagram.workflows.management.session.session import (
        SessionManager,
    )

    sm = SessionManager({
        "session_settings": {"warmup_policy": {"min_action_gap_seconds": floor}},
        "behaviorPolicy": {"profileId": profile},
    })
    values = [sm.get_delay_between_actions() for _ in range(draws)]
    _assert_bounded_without_peak(values, lo, hi)


def test_micro_delay_has_no_edge_spike():
    from taktik.core.social_media.instagram.actions.core.behavior.human_behavior import (
        HumanBehavior,
    )

    human = HumanBehavior()
    human.session_start = time.time()          # no fatigue on top of the draw
    values = [human.gaussian_delay(0.3, 0.8) for _ in range(DRAWS)]
    _assert_bounded_without_peak(values, 0.24, 0.96 * 1.001)
