"""Generic scroll primitives and utility methods."""

import time
import random
from typing import Dict, Any
from loguru import logger

from ...core.base_action import BaseAction
from taktik.core.shared.behavior.gesture_primitives import GestureMixin


class BaseScrollMixin(GestureMixin, BaseAction):
    """Mixin: generic directional scrolls, scroll-to-top/bottom, momentum, smart scroll. The
    humanized flick/drag/curved-swipe primitives (`_strong_flick`/`_long_drag`/`_human_swipe`)
    come from the shared `GestureMixin` (`taktik.core.shared.behavior`), reusable cross-platform."""

    # Base "page" direction -> humanized gesture swipe direction. Page-"down" (advance / reveal the
    # NEXT content) is a finger swipe UP; page-"up" (go back, reveal previous) is a finger swipe DOWN.
    _GESTURE_DIR = {"down": "up", "up": "down"}

    def _scroll(self, direction: str, distance_ratio: float = 0.4, speed: str = "normal") -> bool:
        """Generic scroll — routed through the shared HUMANIZED gesture primitives (`GestureMixin`,
        geometry sampled from real human trajectories: varied start point, drift, duration) instead
        of a fixed-coordinate robotic `swipe_coordinates`.

        Vertical ('down'/'up'): a decisive flick that flings/coasts (default) or a sampled curve
        ('slow'). Horizontal ('left'/'right'): the dedicated humanized horizontal profile.
        `distance_ratio` is interpreted as a fraction of the screen size for the gesture magnitude.
        """
        try:
            if direction in ("down", "up"):
                g_dir = self._GESTURE_DIR[direction]
                distance_px = (distance_ratio * self.screen_height) if distance_ratio else None
                if speed == "slow":
                    ok = self._human_swipe(direction=g_dir, distance_px=distance_px)
                else:
                    ok = self._strong_flick(direction=g_dir, distance_px=distance_px)
                self._human_like_delay("scroll")
                return ok
            if direction in ("left", "right"):
                ok = self._human_horizontal_swipe(direction, distance_ratio or 0.6)
                self._human_like_delay("scroll")
                return ok
            self.logger.error(f"Invalid scroll direction: {direction}")
            return False
        except Exception as e:
            self.logger.error(f"Error scrolling {direction}: {e}")
            return False
    
    def scroll_down(self, distance_ratio: float = 0.4, speed: str = "normal") -> bool:
        return self._scroll('down', distance_ratio, speed)
    
    def scroll_up(self, distance_ratio: float = 0.4, speed: str = "normal") -> bool:
        return self._scroll('up', distance_ratio, speed)
    
    def scroll_left(self, distance_ratio: float = 0.4, speed: str = "normal") -> bool:
        return self._scroll('left', distance_ratio, speed)
    
    def scroll_right(self, distance_ratio: float = 0.4, speed: str = "normal") -> bool:
        return self._scroll('right', distance_ratio, speed)

    def scroll_to_top(self, max_attempts: int = 6) -> bool:
        """Humanized return to the top: decisive down-flicks (a real fling — the content coasts up
        toward the header), with the occasional sampled curve for variety. Never the fixed-coordinate
        robotic swipe, so e.g. landing back on a profile header looks human."""
        self.logger.debug("⬆️ Human scroll to top")
        for _ in range(max_attempts):
            if random.random() < 0.2:
                self._human_swipe(direction="down")
            else:
                self._strong_flick(direction="down")
            self._random_sleep(0.35, 0.7)
        return True

    def scroll_to_bottom(self, max_attempts: int = 10) -> bool:
        self.logger.debug("⬇️ Human scroll to bottom")

        previous_content = None
        no_change_count = 0

        for attempt in range(max_attempts):
            try:
                current_content = str(self.device.device.dump_hierarchy()) if hasattr(self.device, 'device') else f"attempt_{attempt}"
            except Exception:
                current_content = f"attempt_{attempt}"

            if random.random() < 0.2:
                self._human_swipe(direction="up")
            else:
                self._strong_flick(direction="up")

            if current_content == previous_content:
                no_change_count += 1
                if no_change_count >= 3:
                    self.logger.debug("End of content detected")
                    return True
            else:
                no_change_count = 0

            previous_content = current_content
            self._random_sleep(1.0, 2.0)

        return True

    def scroll_horizontally_in_carousel(self, direction: str = "right") -> bool:
        self.logger.debug(f"🔄 Human carousel swipe to {direction}")
        # Carousel "right" = reveal the NEXT slide = a left-moving finger swipe (and vice versa).
        if direction in ("right", "left"):
            return self._human_horizontal_swipe("left" if direction == "right" else "right",
                                                distance_ratio=0.7)
        self.logger.error(f"Invalid direction: {direction}")
        return False

    def scroll_with_momentum(self, direction: str = "down", intensity: str = "medium") -> bool:
        self.logger.debug(f"💨 Human momentum scroll {direction} (intensity: {intensity})")
        dist_ratio = {"light": 0.3, "medium": 0.5, "strong": 0.7}.get(intensity, 0.5)
        # Routes through the humanized _scroll (flick) — distance scaled by intensity.
        return self._scroll(direction, distance_ratio=dist_ratio, speed="fast")

    def get_scroll_position_info(self) -> Dict[str, Any]:
        return {
            'screen_width': self.screen_width,
            'screen_height': self.screen_height,
            'center_x': self.screen_width // 2,
            'center_y': self.screen_height // 2,
            'scroll_stats': self.get_method_stats()
        }
