"""Generic scroll primitives and utility methods."""

import time
import random
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
from lxml import etree

from ...core.base_action import BaseAction
from taktik.core.shared.behavior.gesture_primitives import GestureMixin
from ....ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS as FS
from .post_reading import _BOUNDS_RE


class BaseScrollMixin(GestureMixin, BaseAction):
    """Mixin: generic directional scrolls, scroll-to-top/bottom, momentum, smart scroll. The
    humanized flick/drag/curved-swipe primitives (`_strong_flick`/`_long_drag`/`_human_swipe`)
    come from the shared `GestureMixin` (`taktik.core.shared.behavior`), reusable cross-platform."""

    # Base "page" direction -> humanized gesture swipe direction. Page-"down" (advance / reveal the
    # NEXT content) is a finger swipe UP; page-"up" (go back, reveal previous) is a finger swipe DOWN.
    _GESTURE_DIR = {"down": "up", "up": "down"}

    @staticmethod
    def _node_bounds(node) -> Optional[Tuple[int, int, int, int]]:
        match = _BOUNDS_RE.search(node.get("bounds", ""))
        if not match:
            return None
        bounds = tuple(int(match.group(index)) for index in range(1, 5))
        if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            return None
        return bounds

    def _read_post_action_geometry(self, root=None) -> Dict[str, Any]:
        """Read clickable post-action bounds once for the shared touch-down guard.

        The result is cached for a very short window so a Lab probe can locate Share and execute
        the production drag against the exact same dump. A successful dump with no post markers
        returns an empty exclusion list; a failed dump is distinguishable so the ratio fallback
        can be used only when appropriate.
        """
        if root is None:
            now = time.monotonic()
            cached = getattr(self, "_post_action_geometry_cache", None)
            if cached and now - cached[0] <= 0.25:
                return cached[1]

            try:
                xml = self.device._device.dump_hierarchy()
                root = etree.fromstring(xml.encode("utf-8"))
            except Exception as exc:
                self.logger.debug(f"post action geometry dump failed: {exc}")
                result = {"available": False, "post_visible": False, "bounds": [], "roles": {}}
                self._post_action_geometry_cache = (time.monotonic(), result)
                return result

        row_nodes = []
        post_visible = False
        role_bounds: Dict[str, List[Tuple[int, int, int, int]]] = {}
        all_bounds: List[Tuple[int, int, int, int]] = []

        def add(role: str, bounds: Optional[Tuple[int, int, int, int]]) -> None:
            if bounds is None:
                return
            if bounds not in all_bounds:
                all_bounds.append(bounds)
            values = role_bounds.setdefault(role, [])
            if bounds not in values:
                values.append(bounds)

        for node in root.iter():
            short = node.get("resource-id", "").rsplit("/", 1)[-1]
            if short in FS.gesture_post_marker_ids:
                post_visible = True
            if short in FS.gesture_action_row_ids:
                row_nodes.append(node)
            for role, tokens in FS.gesture_action_id_tokens:
                if short and any(token in short for token in tokens):
                    post_visible = True
                    add(role, self._node_bounds(node))
                    # Instagram often puts the resource-id on an icon whose clickable parent owns
                    # a wider touch target. Protect both when that parent is present in the dump.
                    parent = node.getparent()
                    for _ in range(3):
                        if parent is None:
                            break
                        if (parent.get("clickable") == "true"
                                or (parent.get("class") or "").endswith("Button")):
                            add(role, self._node_bounds(parent))
                            break
                        parent = parent.getparent()
                    break

        # Cover anonymous/count buttons inside the same action row in addition to the named
        # like/comment/share/save affordances.
        for row in row_nodes:
            for node in row.iterdescendants():
                if (node.get("clickable") == "true"
                        or (node.get("class") or "").endswith("Button")):
                    add("button", self._node_bounds(node))

        result = {
            "available": True,
            "post_visible": post_visible,
            "bounds": all_bounds,
            "roles": role_bounds,
        }
        self._post_action_geometry_cache = (time.monotonic(), result)
        return result

    def _remember_post_action_geometry(self, root) -> None:
        """Reuse a hierarchy root already read by feed perception or post reading."""
        self._read_post_action_geometry(root=root)

    def _post_action_bounds(self, role: str) -> List[Tuple[int, int, int, int]]:
        """Expose live action bounds to diagnostics without duplicating selector logic."""
        geometry = self._read_post_action_geometry()
        return list(geometry.get("roles", {}).get(role, []))

    def _gesture_start_exclusion_bounds(self):
        """Platform hook consumed by the shared gesture engine before touch-down."""
        geometry = self._read_post_action_geometry()
        # The gesture is about to change the screen, so this geometry must not serve the next one.
        self._post_action_geometry_cache = None
        if not geometry.get("available"):
            return None
        if not geometry.get("post_visible"):
            return []
        bounds = geometry.get("bounds") or []
        return bounds if bounds else None

    @staticmethod
    def _gesture_fallback_safe_x_band():
        return FS.gesture_fallback_safe_x_band

    def _choose_advance_mode(
        self, context: str, base_drag_probability: float = 0.15
    ) -> Dict[str, Any]:
        """Choose a post-advance gesture through the per-session behaviour memory."""
        state = getattr(self, "behavior_state", None)
        if state is not None and hasattr(state, "choose_scroll_mode"):
            decision = state.choose_scroll_mode(
                context=context,
                base_drag_probability=base_drag_probability,
            )
        else:
            probability = min(1.0, max(0.0, float(base_drag_probability)))
            decision = {
                "context": context,
                "mode": "drag" if random.random() < probability else "flick",
                "style": None,
                "style_changed": False,
                "burst_remaining": 0,
                "drag_probability": round(probability, 3),
                "distance_scale": 1.0,
                "velocity_scale": 1.0,
                "settle_scale": 1.0,
                "dwell_scale": 1.0,
            }
        self._last_advance_behavior = dict(decision)
        return decision

    def _motor_modulation(self, context: str) -> Dict[str, float]:
        """Return session-correlated motor parameters, or neutral legacy values."""
        state = getattr(self, "behavior_state", None)
        if state is not None and hasattr(state, "motor_modulation"):
            return state.motor_modulation(context=context)
        return {
            "distance_scale": 1.0,
            "velocity_scale": 1.0,
            "settle_scale": 1.0,
            "dwell_scale": 1.0,
        }

    def _reading_dwell_scale(self, context: str) -> float:
        """Expose the current session's attention scale to the reading mixin."""
        state = getattr(self, "behavior_state", None)
        if state is not None and hasattr(state, "reading_scale"):
            return float(state.reading_scale(context=context))
        return 1.0

    def _decide_post_framing(
        self,
        *,
        land_ratio: Optional[float],
        confidence: float,
        context: str,
        good_threshold: float,
    ) -> Dict[str, Any]:
        """Route framing through session memory, preserving deterministic legacy fallback."""
        state = getattr(self, "behavior_state", None)
        if state is not None and hasattr(state, "decide_post_framing"):
            decision = state.decide_post_framing(
                land_ratio=land_ratio,
                confidence=confidence,
                context=context,
                good_threshold=good_threshold,
            )
        else:
            needed = land_ratio is not None and land_ratio > good_threshold
            decision = {
                "context": context,
                "style": None,
                "land_ratio": round(land_ratio, 3) if land_ratio is not None else None,
                "confidence": round(float(confidence), 3),
                "needed": needed,
                "correct": needed,
                "probability": 1.0 if needed else 0.0,
                "reason": "legacy_fallback",
                "reaction_delay_s": 0.0,
                "target_ratio": good_threshold * 0.42 if needed else None,
            }
        self._last_framing_behavior = dict(decision)
        return decision

    def _behavior_snapshot(self) -> Dict[str, Any]:
        state = getattr(self, "behavior_state", None)
        if state is not None and hasattr(state, "snapshot"):
            return state.snapshot()
        return {}

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
                decision = self._plan_behavior_gesture("generic_horizontal_scroll", "hswipe")
                ok = self._human_horizontal_swipe(
                    direction, distance_ratio or 0.6,
                    distance_scale=decision["distance_scale"],
                    velocity_scale=decision["velocity_scale"],
                )
                self._human_like_delay("scroll", scale=decision["settle_scale"])
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
