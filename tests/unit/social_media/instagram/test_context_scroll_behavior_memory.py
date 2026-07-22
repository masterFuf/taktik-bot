from types import SimpleNamespace

from taktik.core.social_media.instagram.actions.atomic.scroll.context_scroll import (
    ContextScrollMixin,
)


class _Host(ContextScrollMixin):
    screen_height = 2280

    def __init__(self, result):
        self.result = result
        self.calls = []
        self.logger = SimpleNamespace(
            debug=lambda *_a, **_k: None,
            error=lambda *_a, **_k: None,
        )

    def _plan_behavior_gesture(self, context, gesture):
        self.calls.append(("plan", context, gesture))
        return {
            "distance_scale": 1.04,
            "velocity_scale": 0.90,
            "settle_scale": 1.15,
        }

    def _human_swipe(self, *args, **kwargs):
        self.calls.append(("swipe", args, kwargs))
        return self.result

    def _human_like_delay(self, action_type, scale=1.0):
        self.calls.append(("delay", action_type, scale))


def test_grid_scroll_propagates_scales_and_only_settles_after_success():
    success = _Host(True)
    assert success.scroll_post_grid_down() is True
    assert success.calls[-1] == ("delay", "scroll", 1.15)
    swipe = success.calls[1]
    assert swipe[2]["distance_px"] == 0.5 * 2280 * 1.04
    assert swipe[2]["velocity_scale"] == 0.90

    failure = _Host(False)
    assert failure.scroll_post_grid_down() is False
    assert all(call[0] != "delay" for call in failure.calls)


def test_generic_feed_scroll_does_not_fake_a_settle_after_transport_failure():
    host = _Host(False)

    assert host.scroll_feed_down() is False
    assert all(call[0] != "delay" for call in host.calls)
