"""Humanized device-input gestures — the platform-agnostic toolkit shared by every surface that
scrolls a human feed (Instagram, TikTok, …).

`GestureMixin` provides the three execution profiles, sampled from recorded human trajectories
(`gesture.sample_swipe`) and executed via the raw uiautomator2 device:

  - **`_strong_flick`** — a fast straight `raw.swipe` (very short duration) → a REAL Android fling,
    so the content coasts ~2.5-4x past the finger (a small flick reveals a whole post).
  - **`_long_drag`** — a slow `raw.drag` (1:1 finger track, lifts at ~0 velocity, no coast).
  - **`_human_swipe`** — the older curved multi-point `swipe_points` profile (kept for callers that
    want a sampled curve rather than a decisive flick/drag).

It is a pure mixin (no platform base): the host class must provide `self.device` (a device facade
exposing `_device` = the raw u2 device, plus `swipe_coordinates`), `self.screen_width/height`, and
`self.logger`. The engineering rationale (why `swipe_points` could not fling, why `raw.swipe` does)
is documented in `taktik-docs/bot/security/feed-scroll-engineering.md`.
"""

import time
import random
from typing import Optional

from .gesture import sample_swipe
from taktik.core.shared.telemetry import emit_step


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
                     start_band: Optional[tuple] = None, controlled: bool = False) -> bool:
        """Curved multi-point swipe via `swipe_points` (or the raw touch API when `controlled`).
        Kept for callers that want a sampled curve; the decisive feed advance uses `_strong_flick`.

        NB: `swipe_points` interpolates at constant average velocity and our ease-out makes the
        final segment the slowest, so it does NOT trigger a real fling (the content tracks the
        finger ~1:1). For a true coast use `_strong_flick`."""
        try:
            path, duration = sample_swipe(
                int(self.screen_width), int(self.screen_height),
                direction=direction, distance_px=distance_px, start_band=start_band,
            )
            n_seg = max(1, len(path) - 1)
            raw = getattr(self.device, "_device", None)

            if controlled and raw is not None and hasattr(raw, "touch"):
                t = raw.touch
                sx, sy = path[0]
                per_seg = duration / n_seg
                t.down(sx, sy).sleep(random.uniform(0.09, 0.14))
                for x, y in path[1:]:
                    t.move(x, y).sleep(per_seg)
                t.up(path[-1][0], path[-1][1])
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
                controlled=controlled,
            )
            time.sleep(0.1)
            return True
        except Exception as e:
            self.logger.error(f"Error in human swipe ({direction}): {e}")
            return False

    def _strong_flick(self, direction: str = "up", distance_px: Optional[float] = None,
                      vel_range: tuple = (9000.0, 13000.0)) -> bool:
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
            (sx, sy), (ex, ey) = path[0], path[-1]
            dy = abs(ey - sy) or 1
            duration = min(max(dy / random.uniform(*vel_range), 0.045), 0.10)
            raw = getattr(self.device, "_device", None)
            if raw is not None and hasattr(raw, "swipe"):
                raw.swipe(sx, sy, ex, ey, duration=duration)
            else:
                self.device.swipe_coordinates(sx, sy, ex, ey, duration)
            emit_step(
                "scroll", action="flick", target=direction,
                distance_px=int(dy), duration_ms=round(duration * 1000),
            )
            time.sleep(0.05)
            return True
        except Exception as e:
            self.logger.error(f"Error in strong flick ({direction}): {e}")
            return False

    def _long_drag(self, direction: str = "up", distance_px: Optional[float] = None,
                   vel_range: tuple = (1500.0, 2200.0)) -> bool:
        """A long CONTINUOUS finger-down drag ("keep the finger on the screen and push"). It tracks
        the finger 1:1 and lifts at ~zero velocity (no fling, no coast), landing exactly where the
        finger stops. Starts LOW (but clear of the bottom nav bar) so it has room to travel ~0.8h
        upward. Executed via `raw.drag`; falls back to `swipe_points`, then to a plain swipe."""
        try:
            h = int(self.screen_height)
            target = distance_px if distance_px is not None else random.uniform(0.78, 0.90) * h
            # Start band kept ABOVE the bottom nav bar (top ≈ 0.886h): a drag whose touch-down lands
            # on the Search/Explore tab opens it (and the keyboard) instead of scrolling. 0.78-0.85h
            # gives the drag room to travel ~one post upward while staying clear of the nav.
            path, _ = sample_swipe(int(self.screen_width), h, direction=direction,
                                   distance_px=target, start_band=(0.78 * h, 0.85 * h),
                                   dist_cap_h=0.95)
            (sx, sy), (ex, ey) = path[0], path[-1]
            dy = abs(ey - sy) or 1
            duration = min(max(dy / random.uniform(*vel_range), 0.40), 0.85)
            raw = getattr(self.device, "_device", None)
            if raw is not None and hasattr(raw, "drag"):
                raw.drag(sx, sy, ex, ey, duration=duration)
            elif raw is not None and hasattr(raw, "swipe_points"):
                raw.swipe_points(path, duration / max(1, len(path) - 1))
            else:
                self.device.swipe_coordinates(sx, sy, ex, ey, duration)
            emit_step(
                "scroll", action="drag", target=direction,
                distance_px=int(dy), duration_ms=round(duration * 1000),
            )
            time.sleep(0.08)
            return True
        except Exception as e:
            self.logger.error(f"Error in long drag ({direction}): {e}")
            return False
