"""Instagram-specific scroll — routed through the shared HUMANIZED gesture engine."""

from taktik.core.shared.behavior.gesture_primitives import human_scroll_raw


class ScrollMixin:
    """Mixin: scroll IG-specific (_scroll_down, _scroll_up) — now routed through the shared
    humanized engine (`human_scroll_raw`, geometry sampled from real human trajectories) instead of
    a near-centre fixed swipe. The host holds a bare uiautomator2 device (`self.device`)."""

    def _scroll_down(self, distance: int = 500) -> None:
        """Scroll to reveal the NEXT content (humanized controlled scroll). `distance` is kept for
        back-compat — the gesture magnitude is screen-relative."""
        human_scroll_raw(self.device, "down", distance_ratio=0.4)
        self._human_like_delay('scroll')

    def _scroll_up(self, distance: int = 500) -> None:
        """Scroll back toward the previous content (humanized controlled scroll)."""
        human_scroll_raw(self.device, "up", distance_ratio=0.4)
        self._human_like_delay('scroll')
