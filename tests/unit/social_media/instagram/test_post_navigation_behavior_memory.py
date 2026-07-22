from types import SimpleNamespace

from taktik.core.shared.behavior.session_state import BehaviorSessionState
from taktik.core.social_media.instagram.actions.business.actions.like.post_navigation import (
    PostNavigationMixin,
)


class _Logger:
    def debug(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class _Device:
    @staticmethod
    def get_screen_size():
        return 1080, 2280


class _Scroll:
    def __init__(self):
        self.calls = []

    def _choose_advance_mode(self, context, base_drag_probability):
        self.calls.append(("choose", context, base_drag_probability))
        return {
            "mode": "drag",
            "style": "deliberate",
            "burst_remaining": 2,
            "distance_scale": 1.04,
            "velocity_scale": 0.90,
            "dwell_scale": 1.22,
        }

    def _long_drag(self, **kwargs):
        self.calls.append(("drag", kwargs))
        return True

    def land_on_post_header(self):
        self.calls.append(("frame",))
        return {"corrected": False}


class _Host(PostNavigationMixin):
    def __init__(self):
        self.device = _Device()
        self.scroll_actions = _Scroll()
        self.logger = _Logger()

    @staticmethod
    def _is_in_post_view():
        return True


def test_profile_post_navigation_uses_session_mode_choice(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.post_navigation.time.sleep",
        sleeps.append,
    )
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.post_navigation.content_dwell",
        lambda _chars: 10.0,
    )
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.post_navigation.random.uniform",
        lambda lower, _upper: lower,
    )
    host = _Host()

    assert host._navigate_to_next_post_in_sequence() is True
    assert host.scroll_actions.calls[0] == ("choose", "profile_posts", 0.15)
    assert host.scroll_actions.calls[1][0] == "drag"
    assert host.scroll_actions.calls[1][1]["guard_start"] is True
    assert host.scroll_actions.calls[1][1]["velocity_scale"] == 0.90
    assert host.scroll_actions.calls[1][1]["distance_px"] == 0.80 * 2280 * 1.04
    assert host.scroll_actions.calls[2] == ("frame",)
    assert sleeps == [12.2]


def test_profile_post_flick_keeps_session_reach_below_the_safe_cap(monkeypatch):
    class _FlickScroll(_Scroll):
        def _choose_advance_mode(self, context, base_drag_probability):
            decision = super()._choose_advance_mode(context, base_drag_probability)
            return {**decision, "mode": "flick"}

        def _strong_flick(self, **kwargs):
            self.calls.append(("flick", kwargs))
            return True

    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.post_navigation.time.sleep",
        lambda _seconds: None,
    )
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.post_navigation.random.uniform",
        lambda lower, _upper: lower,
    )
    host = _Host()
    host.scroll_actions = _FlickScroll()

    assert host._navigate_to_next_post_in_sequence() is True

    flick = host.scroll_actions.calls[1]
    assert flick[0] == "flick"
    assert flick[1]["distance_px"] == 0.34 * 2280 * 1.04
    assert flick[1]["velocity_scale"] == 0.90


def test_failed_primary_uses_vertical_retry_never_horizontal_carousel_swipe(monkeypatch):
    class _RetryScroll(_Scroll):
        def _long_drag(self, **kwargs):
            self.calls.append(("drag", kwargs))
            return False

        def _plan_behavior_gesture(self, context, gesture):
            self.calls.append(("plan", context, gesture))
            return {
                "distance_scale": 1.03,
                "velocity_scale": 0.92,
                "settle_scale": 1.10,
                "dwell_scale": 1.20,
            }

        def _human_swipe(self, **kwargs):
            self.calls.append(("controlled", kwargs))
            return True

    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.post_navigation.time.sleep",
        lambda _seconds: None,
    )
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.post_navigation.content_dwell",
        lambda _chars: 0.0,
    )
    host = _Host()
    host.scroll_actions = _RetryScroll()

    assert host._navigate_to_next_post_in_sequence() is True

    assert [call[0] for call in host.scroll_actions.calls] == [
        "choose", "drag", "plan", "controlled", "frame"
    ]
    retry = host.scroll_actions.calls[3][1]
    assert retry["direction"] == "up"
    assert retry["controlled"] is True
    assert retry["start_band"] == (0.78 * 2280, 0.86 * 2280)
    assert retry["guard_start"] is True
    assert retry["velocity_scale"] == 0.92


def test_profile_grid_scroll_uses_the_same_session_timeline(monkeypatch):
    class _GridScroll:
        def __init__(self):
            self.calls = []

        def _plan_behavior_gesture(self, context, gesture):
            self.calls.append(("plan", context, gesture))
            return {
                "distance_scale": 1.04,
                "velocity_scale": 0.90,
                "settle_scale": 1.15,
            }

        def _strong_flick(self, *args, **kwargs):
            self.calls.append(("flick", args, kwargs))
            return True

    sleeps = []
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.post_navigation.time.sleep",
        sleeps.append,
    )
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.post_navigation.random.uniform",
        lambda lower, _upper: lower,
    )
    host = _Host()
    host.scroll_actions = _GridScroll()

    assert host._session_grid_scroll(
        "profile_grid_prescroll", distance_ratio=0.40, coast=True
    ) is True

    assert host.scroll_actions.calls[0] == (
        "plan", "profile_grid_prescroll", "flick"
    )
    flick = host.scroll_actions.calls[1]
    assert flick[1] == ("up",)
    assert flick[2]["distance_px"] == 2280 * 0.40 * 1.04
    assert flick[2]["velocity_scale"] == 0.90
    assert sleeps == [0.45 * 1.15]


def test_failed_vertical_gestures_reach_the_real_next_button_property(monkeypatch):
    clicks = []

    class _RetryFailure(_Scroll):
        def _long_drag(self, **kwargs):
            self.calls.append(("drag", kwargs))
            return False

        def _plan_behavior_gesture(self, context, gesture):
            return {
                "distance_scale": 1.0,
                "velocity_scale": 1.0,
                "settle_scale": 1.0,
                "dwell_scale": 1.0,
            }

        @staticmethod
        def _human_swipe(**_kwargs):
            return False

    class _Button:
        exists = True

        @staticmethod
        def click():
            clicks.append("next")

    class _ButtonDevice(_Device):
        @staticmethod
        def xpath(_selector):
            return _Button()

    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.post_navigation.time.sleep",
        lambda _seconds: None,
    )
    host = _Host()
    host.device = _ButtonDevice()
    host.scroll_actions = _RetryFailure()
    host.post_selectors = type("_Selectors", (), {"next_post_button_selectors": ("next",)})()

    assert host._navigate_to_next_post_in_sequence() is True
    assert clicks == ["next"]


def test_reopen_selection_excludes_the_last_successful_grid_cell_in_session_ram():
    host = object.__new__(PostNavigationMixin)
    host.behavior_state = BehaviorSessionState(seed=7)
    posts = [
        SimpleNamespace(attrib={"content-desc": f"post à la ligne 1, colonne {column}"})
        for column in (1, 2, 3)
    ]

    first = host._choose_session_grid_entry(posts, username="kevin")
    host._remember_session_grid_entry(posts[first], first, username="kevin")
    second = host._choose_session_grid_entry(posts, username="kevin")

    assert second != first
