"""Generic scroll primitives and utility methods."""

import time
import random
from typing import Optional, Dict, Any
from loguru import logger

from ...core.base_action import BaseAction
from .human_gesture import sample_swipe


class BaseScrollMixin(BaseAction):
    """Mixin: generic directional scrolls, scroll-to-top/bottom, momentum, smart scroll."""

    _SPEED_MAP = {'slow': 1.0, 'normal': 0.5, 'fast': 0.2}

    @staticmethod
    def _fling_total(path) -> float:
        """Total fling duration giving a CONSISTENT release velocity (~3200-4200 px/s) so the
        coast is proportional to the flick distance — instead of the wildly variable coast a
        fixed random duration produced (decorrelated velocity → dents-de-scie). Always fast
        enough to register as a real fling."""
        dy = abs(path[-1][1] - path[0][1]) or 1
        return min(max(dy / random.uniform(2800, 3800), 0.06), 0.24)

    def _human_swipe(self, direction: str = "up", distance_px: Optional[float] = None,
                     start_band: Optional[tuple] = None, controlled: bool = False) -> bool:
        """Human-like vertical scroll, curved + vertical-dominant.

        Two profiles:
          - **fling** (default): a fast curved swipe executed *server-side* via `swipe_points`
            (one batched gesture, ~70-130ms) → released at high velocity, so Android triggers a
            real fling and the feed **coasts with momentum** (travels well beyond the finger).
            This is the natural "small flick, big scroll". A large fast swipe is never a tap,
            and dx is capped so it is never a sideways swipe — no anti-tap hold needed.
          - **controlled** (`controlled=True`): a slow even-paced drag via the raw touch API
            that tracks the finger 1:1 and stops on release (no coast) — for precise settles.

        NB: a per-point touch.down/move/up drag is NOT used for the fling — each move is a
        separate slow RPC, which kills the release velocity (no momentum, finger-distance-only
        drag). `start_band` forces the start Y into a safe zone (above an inline reel)."""
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
            time.sleep(0.1)
            return True
        except Exception as e:
            self.logger.error(f"Error in human swipe ({direction}): {e}")
            return False

    def _strong_flick(self, direction: str = "up", distance_px: Optional[float] = None,
                      vel_range: tuple = (9000.0, 13000.0)) -> bool:
        """A decisive fast FLICK that triggers a REAL Android fling so the feed COASTS well
        past the finger (content travels ~2.5-4x the finger distance). This is the fix that
        makes ONE gesture reveal a whole post.

        Why it coasts where `_human_swipe` did not: `swipe_points` interpolates the path at a
        constant average velocity and our ease-OUT bezier makes the FINAL segment the slowest,
        so the release velocity never spikes → Android reads a scroll-and-settle (measured
        coast ratio ~1.0, pure finger displacement). Here we send a straight 2-endpoint
        `raw.swipe(sx,sy,ex,ey, short_duration)`: u2 maps duration→steps=int(dur*200) at 5ms
        each, so a very short duration over a long distance keeps a high, constant velocity
        sustained INTO the lift → a true fling. Geometry (start point, drift cap, edge clamps)
        is still sampled from real data; only the execution is the high-velocity straight line.
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
            time.sleep(0.05)
            return True
        except Exception as e:
            self.logger.error(f"Error in strong flick ({direction}): {e}")
            return False

    def _long_drag(self, direction: str = "up", distance_px: Optional[float] = None,
                   vel_range: tuple = (1500.0, 2200.0)) -> bool:
        """A long CONTINUOUS finger-down drag — the user's "keep the finger on the screen and
        push the post into view". It tracks the finger 1:1 and lifts at ~zero velocity (no
        fling, no coast), landing the post exactly where the finger stops. Starts LOW (near the
        bottom) so it has room to travel ~0.8h upward. Executed via `raw.drag` (even-paced,
        slow release); falls back to a multi-point `swipe_points` track, then to a plain swipe."""
        try:
            h = int(self.screen_height)
            target = distance_px if distance_px is not None else random.uniform(0.78, 0.90) * h
            path, _ = sample_swipe(int(self.screen_width), h, direction=direction,
                                   distance_px=target, start_band=(0.80 * h, 0.90 * h),
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
            time.sleep(0.08)
            return True
        except Exception as e:
            self.logger.error(f"Error in long drag ({direction}): {e}")
            return False

    def _scroll(self, direction: str, distance_ratio: float = 0.4, speed: str = "normal") -> bool:
        """
        Generic scroll method.
        
        Args:
            direction: 'up', 'down', 'left', 'right'
            distance_ratio: Scroll distance as ratio of screen size
            speed: 'slow', 'normal', 'fast'
            
        Returns:
            True if scroll successful, False otherwise
        """
        try:
            duration = self._SPEED_MAP.get(speed, 0.5)
            center_x = self.screen_width // 2
            center_y = self.screen_height // 2
            
            if direction == 'down':
                start_x, start_y = center_x, int(self.screen_height * 0.7)
                end_x, end_y = center_x, int(start_y - (self.screen_height * distance_ratio))
            elif direction == 'up':
                start_x, start_y = center_x, int(self.screen_height * 0.3)
                end_x, end_y = center_x, int(start_y + (self.screen_height * distance_ratio))
            elif direction == 'left':
                start_x, start_y = int(self.screen_width * 0.7), center_y
                end_x, end_y = int(start_x - (self.screen_width * distance_ratio)), center_y
            elif direction == 'right':
                start_x, start_y = int(self.screen_width * 0.3), center_y
                end_x, end_y = int(start_x + (self.screen_width * distance_ratio)), center_y
            else:
                self.logger.error(f"Invalid scroll direction: {direction}")
                return False
            
            self.logger.debug(f"📱 Scrolling {direction}: ({start_x}, {start_y}) → ({end_x}, {end_y}) (speed: {speed})")
            self.device.swipe_coordinates(start_x, start_y, end_x, end_y, duration)
            self._human_like_delay('scroll')
            return True
            
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

    def scroll_to_top(self, max_attempts: int = 5) -> bool:
        self.logger.debug("⬆️ Scrolling to top")
        
        for attempt in range(max_attempts):
            if not self.scroll_up(distance_ratio=0.8, speed="fast"):
                return False
            
            self._random_sleep(0.5, 1.0)
        
        return True
    
    def scroll_to_bottom(self, max_attempts: int = 10) -> bool:
        self.logger.debug("⬇️ Scrolling to bottom")
        
        previous_content = None
        no_change_count = 0
        
        for attempt in range(max_attempts):
            try:
                current_content = str(self.device.device.dump_hierarchy()) if hasattr(self.device, 'device') else f"attempt_{attempt}"
            except Exception:
                current_content = f"attempt_{attempt}"
            
            if not self.scroll_down(distance_ratio=0.6, speed="normal"):
                return False
            
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
        self.logger.debug(f"🔄 Scrolling carousel to {direction}")
        
        if direction == "right":
            return self.scroll_left(distance_ratio=0.8, speed="normal")
        elif direction == "left":
            return self.scroll_right(distance_ratio=0.8, speed="normal")
        else:
            self.logger.error(f"Invalid direction: {direction}")
            return False
    
    def scroll_with_momentum(self, direction: str = "down", intensity: str = "medium") -> bool:
        self.logger.debug(f"💨 Scrolling with momentum {direction} (intensity: {intensity})")
        
        intensity_params = {
            'light': {'distance': 0.3, 'duration': 300},
            'medium': {'distance': 0.5, 'duration': 200},
            'strong': {'distance': 0.7, 'duration': 100}
        }
        
        params = intensity_params.get(intensity, intensity_params['medium'])
        
        if direction == "down":
            return self.scroll_down(distance_ratio=params['distance'], speed="fast")
        elif direction == "up":
            return self.scroll_up(distance_ratio=params['distance'], speed="fast")
        elif direction == "left":
            return self.scroll_left(distance_ratio=params['distance'], speed="fast")
        elif direction == "right":
            return self.scroll_right(distance_ratio=params['distance'], speed="fast")
        else:
            self.logger.error(f"Invalid direction: {direction}")
            return False

    def get_scroll_position_info(self) -> Dict[str, Any]:
        return {
            'screen_width': self.screen_width,
            'screen_height': self.screen_height,
            'center_x': self.screen_width // 2,
            'center_y': self.screen_height // 2,
            'scroll_stats': self.get_method_stats()
        }
