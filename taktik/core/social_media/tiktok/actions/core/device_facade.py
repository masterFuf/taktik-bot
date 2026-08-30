import random
import time
from loguru import logger

from taktik.core.shared.device.facade import BaseDeviceFacade


class DeviceFacade(BaseDeviceFacade):
    """TikTok-specific device facade.

    Inherits common functionality from BaseDeviceFacade — including the SHARED humanization
    engine (human_scroll / human_hswipe / human_tap / human_double_tap). The swipe overrides
    below route through that engine instead of fixed-coordinate raw swipes, so every TikTok
    scroll gets varied start points, curved paths and varied durations (no robotic fingerprint).
    Adds TikTok-specific: click(x, y) (with a small tap jitter), double_click, long_click.
    """

    app_id = 'com.zhiliaoapp.musically'
    _facade_name = 'TikTokDeviceFacade'

    def __init__(self, device):
        super().__init__(device, module_name="tiktok-device-facade")

    # =========================================================================
    # Swipe overrides for TikTok's video UI — HUMANIZED (shared engine)
    #
    # Previously these computed FIXED percentage coordinates (x=30%, y 80%->15%) with a
    # constant duration and called the raw u2 swipe — identical trajectory every time (robotic
    # heatmap fingerprint). They now delegate to the shared humanization engine on the base
    # facade (human_scroll / human_hswipe), keeping the same travel distance but with sampled
    # geometry. `scale` is preserved for call-site compatibility and maps to the travel ratio.
    # =========================================================================

    @staticmethod
    def _scaled_ratio(scale: float, base: float) -> float:
        """Map the legacy `scale` (default 0.8) to a travel ratio, preserving the historical
        distance at scale=0.8 (base) and scaling proportionally. Clamped to a sane band."""
        try:
            return round(min(max((float(scale) / 0.8) * base, 0.35), 0.9), 3)
        except Exception:
            return base

    @staticmethod
    def _list_scroll_ratio(scale: float) -> float:
        """Varied vertical LIST-scroll distance. The controlled-scroll path clamps the travel to the
        engine cap (~0.34 of screen height), so a fixed ratio produced an identical distance every
        call (a fixed-distance fingerprint). Sample a per-call value in the 0.28-0.34 band (kept at/
        below the cap so it is NOT clamped to a constant) → varied distance, max unchanged vs before,
        never longer (no new overshoot risk). Scaled by `scale`."""
        try:
            return round(min(max(random.uniform(0.28, 0.34) * (float(scale) / 0.8), 0.18), 0.34), 3)
        except Exception:
            return 0.31

    #: The session's motor style, injected by the workflow that owns this facade. None means no
    #: session memory -- every scale stays 1.0 and the gestures behave exactly as they did.
    behavior_state = None

    def _motor(self, context: str) -> tuple:
        """(distance_scale, velocity_scale) for the run's current style, WITHOUT spending a beat.

        A session that reads BRISK flicks further and faster than one reading DELIBERATE, and it
        keeps doing so for a whole burst before drifting -- which is what makes a run look like one
        person rather than a fresh coin toss per gesture. The scales come from the same
        `BehaviorSessionState` Instagram uses; TikTok owned one and never asked it anything but the
        dwell.

        Use this only where the beat has ALREADY been spent -- the feed advance asks
        `choose_scroll_mode` for its flick-or-drag and that call is the beat. Everywhere else, use
        `_plan_gesture` instead, or the session reads the same style forever.
        """
        state = getattr(self, "behavior_state", None)
        if state is None or not hasattr(state, "motor_modulation"):
            return 1.0, 1.0
        try:
            motor = state.motor_modulation(context=context)
            return float(motor.get("distance_scale", 1.0)), float(motor.get("velocity_scale", 1.0))
        except Exception:
            return 1.0, 1.0

    def _plan_gesture(self, context: str, gesture: str) -> tuple:
        """Same scales, but this one SPENDS a beat of the session.

        The difference matters more than it reads. `motor_modulation` only looks at the current
        style; `plan_directional_gesture` also advances the burst counter and the energy drift, so
        the style eventually changes. Every TikTok gesture but the feed advance was reading without
        advancing -- a list scrolled for two minutes stayed in the style it started in, which is a
        rhythm as fixed as no rhythm at all.

        It is for gestures whose KIND is already decided: a horizontal swipe is a horizontal swipe,
        there is no flick-or-drag to pick. They still belong to the same burst.
        """
        state = getattr(self, "behavior_state", None)
        if state is None or not hasattr(state, "plan_directional_gesture"):
            return self._motor(context)
        try:
            plan = state.plan_directional_gesture(context=context, gesture=gesture)
            return float(plan.get("distance_scale", 1.0)), float(plan.get("velocity_scale", 1.0))
        except Exception:
            return 1.0, 1.0

    def swipe_up(self, scale: float = 0.8, coast: bool = False):
        """Advance the feed / scroll a list DOWN — humanized. TikTok 'swipe up' (finger moves up)
        reveals the NEXT content = page 'down'.

        `coast=True` fires a REAL fling (sampled distance + velocity) — the natural gesture for the
        video FEED, whose pager snaps to the next video regardless of strength, so distance/velocity
        vary (no fixed-distance fingerprint) and it never advances two. `coast=False` (default) is a
        controlled scroll for LISTS (followers/search/scraping/DM), where a fling would overshoot.

        Both carry the session's motor style: the per-call variation was already there, what was
        missing is that successive gestures had nothing in common."""
        # The coast path's beat was already spent by `choose_scroll_mode`, which is what picked
        # `coast` in the first place; the list path has no such call, so it spends its own.
        d, v = (self._motor("tiktok_feed_advance") if coast
                else self._plan_gesture("tiktok_list_scroll_down", "controlled_swipe"))
        if coast:
            self.human_scroll("down", coast=True, distance_scale=d, velocity_scale=v)
        else:
            self.human_scroll("down", distance_ratio=self._list_scroll_ratio(scale),
                              distance_scale=d, velocity_scale=v)

    def swipe_down(self, scale: float = 0.8, coast: bool = False):
        """Go back / scroll a list UP — humanized. Finger moves down = reveal PREVIOUS = page 'up'.
        `coast=True` flings (video feed, snaps to previous); `coast=False` is a controlled list scroll."""
        d, v = (self._motor("tiktok_feed_back") if coast
                else self._plan_gesture("tiktok_list_scroll_up", "controlled_swipe"))
        if coast:
            self.human_scroll("up", coast=True, distance_scale=d, velocity_scale=v)
        else:
            self.human_scroll("up", distance_ratio=self._list_scroll_ratio(scale),
                              distance_scale=d, velocity_scale=v)

    def swipe_left(self, scale: float = 0.8):
        """Reveal the NEXT horizontal slide — humanized. Finger moves left."""
        d, v = self._plan_gesture("tiktok_swipe_left", "hswipe")
        self.human_hswipe("left", distance_ratio=self._scaled_ratio(scale, 0.60),
                          distance_scale=d, velocity_scale=v)

    def swipe_right(self, scale: float = 0.8):
        """Reveal the PREVIOUS horizontal slide — humanized. Finger moves right."""
        d, v = self._plan_gesture("tiktok_swipe_right", "hswipe")
        self.human_hswipe("right", distance_ratio=self._scaled_ratio(scale, 0.60),
                          distance_scale=d, velocity_scale=v)

    # =========================================================================
    # TikTok-specific: click at coordinates (different signature from base)
    # =========================================================================

    @staticmethod
    def _jitter_point(x: int, y: int, spread: float = 4.0, cap: int = 8) -> tuple:
        """Small gaussian jitter around a target point so repeated coordinate taps never land on
        the exact same pixel (removes the touch-heatmap fingerprint). Kept small (±cap px) so it
        stays inside the intended button. Prefer human_tap(bounds) when element bounds are known."""
        dx = max(-cap, min(cap, int(random.gauss(0, spread))))
        dy = max(-cap, min(cap, int(random.gauss(0, spread))))
        return x + dx, y + dy

    def click(self, x: int, y: int):
        """Tap at (x, y) with a small human jitter (never the exact same pixel twice)."""
        try:
            jx, jy = self._jitter_point(x, y)
            self._device.click(jx, jy)
            time.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Error clicking at ({x}, {y}): {e}")
            raise
