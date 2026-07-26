"""Humanized device-input gestures — the platform-agnostic toolkit shared by every surface that
scrolls a human feed (Instagram, TikTok, …).

`GestureMixin` provides the three execution profiles, sampled from recorded human trajectories
(`gesture.sample_swipe`) and executed via the raw uiautomator2 device:

  - **`_strong_flick`** — a fast straight `raw.swipe` (very short duration) → a REAL Android fling,
    so the content coasts ~2.5-4x past the finger (a small flick reveals a whole post).
  - **`_long_drag`** — a slow low-level `raw.touch` path (1:1 finger track, lifts at ~0
    velocity, no coast, and never waits through Android's long-press timeout).
  - **`_human_swipe`** — the older curved multi-point `swipe_points` profile (kept for callers that
    want a sampled curve rather than a decisive flick/drag).

It is a pure mixin (no platform base): the host class must provide `self.device` (a device facade
exposing `_device` = the raw u2 device, plus `swipe_coordinates`), `self.screen_width/height`, and
`self.logger`. The engineering rationale (why `swipe_points` could not fling, why `raw.swipe` does)
is documented in `internal docs`.
"""

import time
import random
import math
from typing import List, Optional, Sequence, Tuple

from loguru import logger as _gesture_logger

from .gesture import sample_swipe
from taktik.core.shared.telemetry import emit_step


_Bounds = Tuple[int, int, int, int]


def _translate_path(
    path: Sequence[Sequence[int]],
    start: Tuple[int, int],
    screen_w: int,
    screen_h: int,
) -> List[List[int]]:
    """Translate a sampled path to ``start`` while keeping every point on-screen."""
    if not path:
        return []
    dx, dy = int(start[0]) - int(path[0][0]), int(start[1]) - int(path[0][1])
    x_min, x_max = int(0.04 * screen_w), int(0.96 * screen_w)
    y_min, y_max = int(0.04 * screen_h), int(0.96 * screen_h)
    return [
        [min(max(int(x) + dx, x_min), x_max), min(max(int(y) + dy, y_min), y_max)]
        for x, y in path
    ]


def _normalise_bounds(bounds: Sequence[Sequence[int]]) -> List[_Bounds]:
    valid: List[_Bounds] = []
    for raw in bounds:
        try:
            left, top, right, bottom = (int(value) for value in raw)
        except (TypeError, ValueError):
            continue
        if right > left and bottom > top:
            valid.append((left, top, right, bottom))
    return valid


def _relocate_path_outside_bounds(
    path: Sequence[Sequence[int]],
    screen_w: int,
    screen_h: int,
    avoid_bounds: Sequence[Sequence[int]],
    *,
    rng=None,
) -> Tuple[List[List[int]], bool]:
    """Move a colliding touch-down into the widest free horizontal gap.

    The obstacle geometry comes from the owning platform's live UI dump. Only ratio-based screen
    margins live here; no platform coordinate or selector leaks into the shared gesture engine.
    Translating the complete path preserves its sampled drift and curvature.
    """
    guarded = [list(point) for point in path]
    bounds = _normalise_bounds(avoid_bounds)
    if not guarded or not bounds:
        return guarded, False

    rng = rng or random
    sx, sy = guarded[0]
    pad_x = max(2, int(round(0.012 * screen_w)))
    pad_y = max(2, int(round(0.008 * screen_h)))
    crossing = [
        (max(0, left - pad_x), min(screen_w, right + pad_x))
        for left, top, right, bottom in bounds
        if top - pad_y <= sy <= bottom + pad_y
    ]
    if not crossing or not any(left <= sx <= right for left, right in crossing):
        return guarded, False

    # Keep the translated curve inside the same ratio-based screen envelope as sample_swipe.
    x_offsets = [int(x) - sx for x, _ in guarded]
    safe_left = max(int(0.06 * screen_w), int(0.04 * screen_w) - min(x_offsets))
    safe_right = min(int(0.94 * screen_w), int(0.96 * screen_w) - max(x_offsets))
    if safe_right <= safe_left:
        return guarded, False

    intervals = sorted(
        (max(safe_left, left), min(safe_right, right))
        for left, right in crossing
        if right >= safe_left and left <= safe_right
    )
    merged: List[List[int]] = []
    for left, right in intervals:
        if not merged or left > merged[-1][1]:
            merged.append([left, right])
        else:
            merged[-1][1] = max(merged[-1][1], right)

    gaps: List[Tuple[int, int]] = []
    cursor = safe_left
    for left, right in merged:
        if left > cursor:
            gaps.append((cursor, left))
        cursor = max(cursor, right)
    if cursor < safe_right:
        gaps.append((cursor, safe_right))
    gaps = [gap for gap in gaps if gap[1] - gap[0] >= max(4, int(0.025 * screen_w))]
    if not gaps:
        return guarded, False

    # The widest blank span is normally the media area between the left action cluster and Save.
    left, right = max(gaps, key=lambda gap: gap[1] - gap[0])
    inset = 0.25 * (right - left)
    safe_x = int(round(rng.uniform(left + inset, right - inset)))
    return _translate_path(guarded, (safe_x, sy), screen_w, screen_h), True


def _move_path_into_x_band(
    path: Sequence[Sequence[int]],
    screen_w: int,
    screen_h: int,
    band: Tuple[float, float],
    *,
    rng=None,
) -> Tuple[List[List[int]], bool]:
    """Fallback when a post is visible but its action bounds could not be read."""
    guarded = [list(point) for point in path]
    if not guarded:
        return guarded, False
    rng = rng or random
    lo, hi = sorted(float(value) for value in band)
    if hi <= 1.0:
        lo, hi = lo * screen_w, hi * screen_w
    sx, sy = guarded[0]
    if lo <= sx <= hi:
        return guarded, False
    safe_x = int(round(rng.uniform(lo, hi)))
    return _translate_path(guarded, (safe_x, sy), screen_w, screen_h), True


def _touch_move_path(
    path: Sequence[Sequence[int]], screen_h: int, *, rng=None
) -> List[List[int]]:
    """Return move points whose first event immediately clears Android's touch-slop.

    The first displacement varies above 3% of screen height. It is injected without a preceding
    sleep, preventing Android from classifying the contact as a long-press while avoiding a fixed
    slop-edge fingerprint.
    """
    points = [list(point) for point in path]
    if len(points) < 2:
        return points[1:]
    rng = rng or random
    sx, sy = points[0]
    ex, ey = points[-1]
    total = math.hypot(ex - sx, ey - sy)
    if total <= 0:
        return points[1:]
    exit_distance = min(total, rng.uniform(0.032, 0.045) * screen_h)
    ratio = exit_distance / total
    first = [int(round(sx + (ex - sx) * ratio)), int(round(sy + (ey - sy) * ratio))]
    moves = [first]
    for point in points[1:]:
        if math.hypot(point[0] - sx, point[1] - sy) > exit_distance * 1.05:
            moves.append(point)
    if moves[-1] != points[-1]:
        moves.append(points[-1])
    return moves


class GestureMixin:
    """Mixin of humanized scroll/drag/flick primitives. Host must expose `self.device`,
    `self.screen_width`, `self.screen_height`, `self.logger`."""

    @staticmethod
    def _fling_total(path) -> float:
        """Total fling duration giving a CONSISTENT release velocity (~2800-3800 px/s) so the coast
        is proportional to the flick distance — instead of the wildly variable coast a fixed random
        duration produced. Used by the legacy `_human_swipe` profile."""
        dy = abs(path[-1][1] - path[0][1]) or 1
        return min(max(dy / random.uniform(2800, 3800), 0.06), 0.24)

    def _human_swipe(self, direction: str = "up", distance_px: Optional[float] = None,
                     start_band: Optional[tuple] = None, controlled: bool = False,
                     guard_start: bool = False,
                     velocity_scale: float = 1.0) -> bool:
        """Curved multi-point swipe via `swipe_points` (or the raw touch API when `controlled`).
        Kept for callers that want a sampled curve; the decisive feed advance uses `_strong_flick`.

        NB: `swipe_points` interpolates at constant average velocity and our ease-out makes the
        final segment the slowest, so it does NOT trigger a real fling (the content tracks the
        finger ~1:1). For a true coast use `_strong_flick`."""
        try:
            path, duration = sample_swipe(
                int(self.screen_width), int(self.screen_height),
                direction=direction, distance_px=distance_px, start_band=start_band,
                # Controlled 1:1 gestures often need half to two-thirds of a screen. The historical
                # 0.34h cap was tuned for the coasting curve and silently shortened grid/retry drags.
                dist_cap_h=0.95 if controlled else 0.34,
            )
            path = self._prepare_gesture_path(path, guard_start=guard_start)
            speed = min(1.50, max(0.60, float(velocity_scale)))
            duration = duration / speed
            n_seg = max(1, len(path) - 1)
            raw = getattr(self.device, "_device", None)

            touch = self._touch_api(raw) if controlled else None
            if touch is not None:
                self._execute_touch_path(touch, path, duration)
            elif raw is not None and hasattr(raw, "swipe_points"):
                # swipe_points `duration` is injected PER SEGMENT (total = duration × segments).
                total = duration if controlled else self._fling_total(path)
                raw.swipe_points(path, total / n_seg)
            else:
                self.device.swipe_coordinates(path[0][0], path[0][1], path[-1][0], path[-1][1],
                                              duration if controlled else self._fling_total(path))
            emit_step(
                "scroll", action="curve", target=direction,
                distance_px=int(abs(path[-1][1] - path[0][1])), points=len(path),
                controlled=controlled, velocity_scale=round(speed, 3),
            )
            time.sleep(0.1)
            return True
        except Exception as e:
            self.logger.error(f"Error in human swipe ({direction}): {e}")
            return False

    def _strong_flick(self, direction: str = "up", distance_px: Optional[float] = None,
                      vel_range: tuple = (9000.0, 13000.0),
                      guard_start: bool = False,
                      velocity_scale: float = 1.0) -> bool:
        """A decisive fast FLICK that triggers a REAL Android fling so the content COASTS well past
        the finger (~2.5-4x the finger distance) — one gesture reveals a whole post.

        Why it coasts where `_human_swipe` did not: a straight 2-endpoint `raw.swipe(sx,sy,ex,ey,
        short_duration)` keeps a high, constant velocity sustained INTO the lift (u2 maps
        duration→steps=int(dur*200) at 5ms each), so a very short duration over a long distance is a
        true fling. Geometry (start point, drift cap, edge clamps incl. the bottom-nav guard) is
        still sampled from real data; only the execution is the high-velocity straight line.
        `vel_range` is the release velocity in px/s (Lab-calibrated; far above the fling floor)."""
        try:
            path, _ = sample_swipe(int(self.screen_width), int(self.screen_height),
                                   direction=direction, distance_px=distance_px,
                                   dist_cap_h=0.45)
            path = self._prepare_gesture_path(path, guard_start=guard_start)
            (sx, sy), (ex, ey) = path[0], path[-1]
            dy = abs(ey - sy) or 1
            speed = min(1.50, max(0.50, float(velocity_scale)))
            scaled_vel_range = tuple(float(value) * speed for value in vel_range)
            # Randomise the FLOOR so short flicks aren't all clamped to an identical 45ms — on a
            # video feed most flicks are short, so a hard floor makes the duration a constant
            # fingerprint. 45-75ms stays a decisive fling (high velocity into the lift).
            duration = min(
                max(dy / random.uniform(*scaled_vel_range), random.uniform(0.045, 0.075)),
                0.11,
            )
            raw = getattr(self.device, "_device", None)
            if raw is not None and hasattr(raw, "swipe"):
                raw.swipe(sx, sy, ex, ey, duration=duration)
            else:
                self.device.swipe_coordinates(sx, sy, ex, ey, duration)
            emit_step(
                "scroll", action="flick", target=direction,
                distance_px=int(dy), duration_ms=round(duration * 1000),
                velocity_scale=round(speed, 3),
            )
            time.sleep(0.05)
            return True
        except Exception as e:
            self.logger.error(f"Error in strong flick ({direction}): {e}")
            return False

    def _long_drag(self, direction: str = "up", distance_px: Optional[float] = None,
                   vel_range: tuple = (1500.0, 2200.0),
                   start_point: Optional[Tuple[int, int]] = None,
                   guard_start: bool = False,
                   velocity_scale: float = 1.0) -> bool:
        """A long CONTINUOUS finger-down drag ("keep the finger on the screen and push"). It tracks
        the finger 1:1 and lifts at ~zero velocity (no fling, no coast), landing exactly where the
        finger stops. Starts LOW (but clear of the bottom nav bar) so it has room to travel ~0.8h
        upward. Executed as low-level touch events whose first move clears touch-slop immediately;
        falls back to `swipe_points`, then to a plain swipe."""
        try:
            h = int(self.screen_height)
            target = distance_px if distance_px is not None else random.uniform(0.78, 0.90) * h
            # Start band kept ABOVE the bottom nav bar (top ≈ 0.886h): a drag whose touch-down lands
            # on the Search/Explore tab opens it (and the keyboard) instead of scrolling. 0.78-0.85h
            # gives the drag room to travel ~one post upward while staying clear of the nav.
            path, _ = sample_swipe(int(self.screen_width), h, direction=direction,
                                   distance_px=target, start_band=(0.78 * h, 0.85 * h),
                                   dist_cap_h=0.95)
            path = self._prepare_gesture_path(
                path, start_point=start_point, guard_start=guard_start
            )
            (sx, sy), (ex, ey) = path[0], path[-1]
            dy = abs(ey - sy) or 1
            speed = min(1.50, max(0.50, float(velocity_scale)))
            scaled_vel_range = tuple(float(value) * speed for value in vel_range)
            duration = min(max(dy / random.uniform(*scaled_vel_range), 0.40), 0.85)
            raw = getattr(self.device, "_device", None)
            touch = self._touch_api(raw)
            if touch is not None:
                self._execute_touch_path(touch, path, duration)
            elif raw is not None and hasattr(raw, "swipe_points"):
                raw.swipe_points(path, duration / max(1, len(path) - 1))
            else:
                self.device.swipe_coordinates(sx, sy, ex, ey, duration)
            emit_step(
                "scroll", action="drag", target=direction,
                distance_px=int(dy), duration_ms=round(duration * 1000),
                velocity_scale=round(speed, 3),
            )
            time.sleep(0.08)
            return True
        except Exception as e:
            self.logger.error(f"Error in long drag ({direction}): {e}")
            return False

    @staticmethod
    def _touch_api(raw):
        """Return a complete u2 low-level touch API, or None so callers use their fallback."""
        if raw is None:
            return None
        try:
            touch = getattr(raw, "touch", None)
        except Exception:
            return None
        if touch is None or not all(hasattr(touch, name) for name in ("down", "move", "up", "sleep")):
            return None
        return touch

    def _execute_touch_path(self, touch, path: Sequence[Sequence[int]], duration: float) -> None:
        """Inject DOWN -> immediate MOVE -> paced path -> near-zero-velocity UP."""
        sx, sy = path[0]
        moves = _touch_move_path(path, int(self.screen_height))
        if not moves:
            return
        per_move = duration / max(1, len(moves))
        last_x, last_y = sx, sy
        down_sent = False
        try:
            touch.down(sx, sy)
            down_sent = True
            # Deliberately no sleep here: leave touch-slop before Android's longPressTimeout.
            for x, y in moves:
                touch.move(x, y)
                last_x, last_y = x, y
                touch.sleep(per_move)
            touch.up(path[-1][0], path[-1][1])
            down_sent = False
        finally:
            if down_sent:
                try:
                    touch.up(last_x, last_y)
                except Exception:
                    pass

    def _prepare_gesture_path(
        self,
        path: Sequence[Sequence[int]],
        start_point: Optional[Tuple[int, int]] = None,
        guard_start: bool = False,
    ) -> List[List[int]]:
        """Apply an optional requested start, then the platform-owned interactive-zone guard."""
        screen_w, screen_h = int(self.screen_width), int(self.screen_height)
        sampled_start = tuple(path[0])
        prepared = [list(point) for point in path]
        if start_point is not None:
            prepared = _translate_path(prepared, start_point, screen_w, screen_h)
        requested_start = tuple(prepared[0])
        source = "none"

        provider = getattr(self, "_gesture_start_exclusion_bounds", None)
        if guard_start and callable(provider):
            try:
                bounds = provider()
            except Exception as exc:
                bounds = None
                try:
                    self.logger.debug(f"gesture start bounds unavailable: {exc}")
                except Exception:
                    pass
            if bounds is None:
                fallback_provider = getattr(self, "_gesture_fallback_safe_x_band", None)
                if callable(fallback_provider):
                    prepared, _ = _move_path_into_x_band(
                        prepared, screen_w, screen_h, fallback_provider()
                    )
                    source = "fallback_band"
            else:
                prepared, moved = _relocate_path_outside_bounds(
                    prepared, screen_w, screen_h, bounds
                )
                if bounds:
                    source = "ui_bounds" if moved else "ui_bounds_clear"

        final_start = tuple(prepared[0])
        self._last_gesture_start = {
            "sampled": sampled_start,
            "requested": requested_start,
            "final": final_start,
            "adjusted": final_start != requested_start,
            "source": source,
        }
        return prepared

    def _human_horizontal_swipe(self, direction: str = "left", distance_ratio: float = 0.6,
                                y_ratio: Optional[float] = None,
                                bounds: Optional[_Bounds] = None,
                                distance_scale: float = 1.0,
                                velocity_scale: float = 1.0) -> bool:
        """Humanized HORIZONTAL swipe (carousels, story-advance, story/highlight trays).
        `sample_swipe` is vertical-only (it hard-caps horizontal drift so a feed scroll never reads
        as a story-camera swipe), so horizontal motion needs its own profile: a varied start point
        (never dead-centre), a small vertical wobble, and a varied duration — instead of a
        fixed-coordinate robotic swipe. `direction="left"` = finger moves left → next slide;
        `"right"` = previous. `y_ratio` pins the swipe row (e.g. a top story tray at ~0.17h) when the
        target is not mid-screen; default samples the mid band so a generic carousel still varies."""
        try:
            w, h = int(self.screen_width), int(self.screen_height)
            reach = min(1.25, max(0.75, float(distance_scale)))
            speed = min(1.50, max(0.60, float(velocity_scale)))
            if bounds is not None:
                left, top, right, bottom = (int(value) for value in bounds)
                left, right = max(0, left), min(w, right)
                top, bottom = max(0, top), min(h, bottom)
                if right <= left or bottom <= top:
                    raise ValueError(f"invalid horizontal swipe bounds: {bounds}")
                local_w, local_h = right - left, bottom - top
                sy = (top + bottom) / 2 + local_h * random.uniform(-0.025, 0.025)
                ey = sy + min(0.02 * h, 0.04 * local_h) * random.uniform(-1.0, 1.0)
                dist = local_w * distance_ratio * reach * random.uniform(0.9, 1.05)
                if direction == "left":
                    sx = left + local_w * random.uniform(0.78, 0.86)
                    ex = sx - dist
                else:
                    sx = left + local_w * random.uniform(0.14, 0.22)
                    ex = sx + dist
                ex = min(max(ex, left + 0.05 * local_w), right - 0.05 * local_w)
            else:
                base_y = y_ratio if y_ratio is not None else random.uniform(0.42, 0.58)
                sy = h * base_y
                ey = sy + h * random.uniform(-0.02, 0.02)      # slight vertical wobble
                dist = w * distance_ratio * reach * random.uniform(0.9, 1.05)
                if direction == "left":
                    sx = w * random.uniform(0.78, 0.88)
                    ex = sx - dist
                else:
                    sx = w * random.uniform(0.12, 0.22)
                    ex = sx + dist
                ex = min(max(ex, 0.05 * w), 0.95 * w)
            duration = min(0.50, max(0.16, random.uniform(0.22, 0.38) / speed))
            raw = getattr(self.device, "_device", None)
            if raw is not None and hasattr(raw, "swipe"):
                raw.swipe(int(sx), int(sy), int(ex), int(ey), duration=duration)
            else:
                self.device.swipe_coordinates(int(sx), int(sy), int(ex), int(ey), duration)
            emit_step(
                "scroll", action="hswipe", target=direction,
                distance_px=int(abs(ex - sx)), duration_ms=round(duration * 1000),
                distance_scale=round(reach, 3), velocity_scale=round(speed, 3),
            )
            time.sleep(0.05)
            return True
        except Exception as e:
            self.logger.error(f"Error in horizontal swipe ({direction}): {e}")
            return False


# =============================================================================
# Module-level humanized scroll for call-sites that hold a BARE uiautomator2
# device (no device facade). Same single engine as `GestureMixin` /
# `BaseDeviceFacade.human_scroll` — a thin adapter lets the bare device satisfy
# the mixin's host contract, so there is still ONE humanization source.
# =============================================================================

_PAGE_TO_GESTURE = {"down": "up", "up": "down"}


class _RawDeviceAdapter:
    """Wraps a bare uiautomator2 device so it looks like a device facade to `GestureMixin`
    (which reaches `self.device._device` for the raw API and `self.device.swipe_coordinates`)."""

    def __init__(self, raw):
        self._device = raw

    def swipe_coordinates(self, x1, y1, x2, y2, duration: float = 0.5):
        self._device.swipe(x1, y1, x2, y2, duration=duration)


class _RawGestureHost(GestureMixin):
    pass


def _raw_host(device, logger=None) -> _RawGestureHost:
    """Build a GestureMixin host from EITHER a device facade (already exposes `_device` +
    `swipe_coordinates`) OR a bare uiautomator2 device (wrapped in the adapter) — so the raw
    helpers are safe to call whatever device type a surface happens to hold."""
    host = _RawGestureHost()
    if hasattr(device, "swipe_coordinates") and hasattr(device, "_device"):
        host.device = device          # a device facade
        raw = device._device
    else:
        host.device = _RawDeviceAdapter(device)   # a bare u2 device
        raw = device
    host.logger = logger or _gesture_logger
    w = h = None
    try:
        if hasattr(device, "get_screen_size"):
            w, h = device.get_screen_size()
        else:
            w, h = raw.window_size()
    except Exception:
        try:
            info = raw.info
            w, h = info['displayWidth'], info['displayHeight']
        except Exception:
            w, h = 1080, 1920
    host.screen_width, host.screen_height = int(w), int(h)
    return host


def human_scroll_raw(raw_device, direction: str = "down", distance_ratio: Optional[float] = None,
                     coast: bool = False, logger=None) -> bool:
    """Humanized VERTICAL scroll for a bare u2 device. `direction='down'` advances (reveals the
    NEXT content), `'up'` goes back. `coast=True` flings; `coast=False` (default) is a 1:1
    controlled curve that preserves a precise travel distance. Mirrors `device.human_scroll`."""
    host = _raw_host(raw_device, logger)
    g_dir = _PAGE_TO_GESTURE.get(direction, "up")
    distance_px = (distance_ratio * host.screen_height) if distance_ratio else None
    if coast:
        return host._strong_flick(direction=g_dir, distance_px=distance_px)
    return host._human_swipe(direction=g_dir, distance_px=distance_px)


def human_hswipe_raw(raw_device, direction: str = "left", distance_ratio: float = 0.6,
                     y_ratio: Optional[float] = None, logger=None,
                     distance_scale: float = 1.0, velocity_scale: float = 1.0) -> bool:
    """Humanized HORIZONTAL swipe for a bare u2 device. `direction='left'` reveals the NEXT slide,
    `'right'` the previous. Mirrors `device.human_hswipe`."""
    return _raw_host(raw_device, logger)._human_horizontal_swipe(
        direction, distance_ratio, y_ratio=y_ratio,
        distance_scale=distance_scale, velocity_scale=velocity_scale,
    )


def human_drag_between_raw(raw_device, start: Tuple[int, int], end: Tuple[int, int],
                           duration: float = 0.65, logger=None) -> bool:
    """Continuous finger-down drag from `start` to `end` that TRACKS the finger 1:1 and lifts at
    near-zero velocity — press, hold, accompany, release.

    Distinct from a swipe on purpose. `swipe_coordinates` sends a coarse down/move/up: Android
    reads it as a FLING and lets the widget settle wherever its own velocity thresholds say, which
    on a bottom sheet means dropping exactly one state (expanded -> collapsed) however far the
    gesture travelled. A drag that stays down and reports many intermediate positions carries the
    sheet with it, so at release the sheet is already at the bottom and settles closed.

    Endpoints are given, not sampled: callers here are aiming at a grab bar or a sheet's content,
    not scrolling a page. `_long_drag` owns the sampled-endpoint case.
    """
    host = _raw_host(raw_device, logger)
    sx, sy = int(start[0]), int(start[1])
    ex, ey = int(end[0]), int(end[1])

    # Enough intermediate points that the widget sees a tracked finger rather than a jump.
    steps = max(12, min(32, abs(ey - sy) // 40))
    path = [
        [round(sx + (ex - sx) * (i / steps)), round(sy + (ey - sy) * (i / steps))]
        for i in range(steps + 1)
    ]

    raw = getattr(host.device, "_device", None) or raw_device
    try:
        touch = host._touch_api(raw)
        if touch is not None:
            host._execute_touch_path(touch, path, duration)
        elif hasattr(raw, "swipe_points"):
            raw.swipe_points(path, duration / max(1, len(path) - 1))
        else:
            host.device.swipe_coordinates(sx, sy, ex, ey, duration)
        emit_step(
            "scroll", action="drag", target="down" if ey > sy else "up",
            distance_px=int(abs(ey - sy)), duration_ms=round(duration * 1000),
            points=len(path),
        )
        return True
    except Exception as exc:
        host.logger.error(f"Error in drag between points: {exc}")
        return False
