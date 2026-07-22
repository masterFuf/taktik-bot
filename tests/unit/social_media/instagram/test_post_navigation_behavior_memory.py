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

    def info(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def success(self, *_args, **_kwargs):
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


def test_reopen_selection_excludes_every_successful_grid_cell_in_profile_visit():
    host = object.__new__(PostNavigationMixin)
    host.behavior_state = BehaviorSessionState(seed=7)
    posts = [
        SimpleNamespace(attrib={"content-desc": f"post à la ligne 1, colonne {column}"})
        for column in (1, 2, 3)
    ]

    chosen = []
    for _ in posts:
        index = host._choose_session_grid_entry(
            posts, username="kevin", require_unseen=True
        )
        assert index is not None
        assert index not in chosen
        chosen.append(index)
        host._remember_session_grid_entry(posts[index], index, username="kevin")

    assert host._choose_session_grid_entry(
        posts, username="kevin", require_unseen=True
    ) is None


def test_vertical_profile_advance_is_also_remembered_before_reel_exit():
    host = object.__new__(PostNavigationMixin)
    host.behavior_state = BehaviorSessionState(seed=9)
    opened = SimpleNamespace(
        attrib={"content-desc": "post à la ligne 1, colonne 2"}
    )

    host._remember_session_grid_entry(opened, 1, username="kevin")
    host._remember_sequential_profile_post()

    keys = [
        item["key"]
        for item in host.behavior_state.grid_entry_history
        if item["context"] == "kevin"
    ]
    assert keys == ["kevin:position:2", "kevin:position:3"]


def test_reel_reentry_scrolls_grid_to_find_a_new_absolute_position(monkeypatch):
    first_view = [
        SimpleNamespace(attrib={"content-desc": f"post à la ligne 1, colonne {column}"})
        for column in (1, 2)
    ]
    second_view = [
        first_view[1],
        SimpleNamespace(attrib={"content-desc": "post à la ligne 1, colonne 3"}),
    ]
    host = object.__new__(PostNavigationMixin)
    host.behavior_state = BehaviorSessionState(seed=11)
    host.logger = _Logger()
    host.detection_selectors = SimpleNamespace(post_thumbnail_selectors=("thumb",))
    host.scroll_actions = SimpleNamespace(
        _plan_behavior_gesture=lambda *_args, **_kwargs: {}
    )
    opened = []
    scrolls = []

    host._remember_session_grid_entry(first_view[0], 0, username="kevin")
    host._remember_session_grid_entry(first_view[1], 1, username="kevin")
    host._visible_grid_thumbnails = lambda _selector: second_view if scrolls else first_view
    host._session_grid_scroll = lambda *_args, **_kwargs: (scrolls.append("up") or True)
    host._human_tap_grid_thumbnail = lambda target: (opened.append(target) or True)
    host._is_in_post_view = lambda: True
    host._emit_entry_decision = lambda *_args, **_kwargs: None
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.post_navigation.time.sleep",
        lambda _seconds: None,
    )

    assert host._open_entry_post_of_profile(
        posts_count=3, username="kevin", reopening=True
    ) is True
    assert scrolls == ["up"]
    assert opened == [second_view[1]]


def test_reel_reentry_stops_when_visible_grid_is_exhausted(monkeypatch):
    posts = [
        SimpleNamespace(attrib={"content-desc": f"post à la ligne 1, colonne {column}"})
        for column in (1, 2)
    ]
    host = object.__new__(PostNavigationMixin)
    host.behavior_state = BehaviorSessionState(seed=13)
    host.logger = _Logger()
    host.detection_selectors = SimpleNamespace(post_thumbnail_selectors=("thumb",))
    host._remember_session_grid_entry(posts[0], 0, username="kevin")
    host._remember_session_grid_entry(posts[1], 1, username="kevin")
    host._visible_grid_thumbnails = lambda _selector: posts
    host._session_grid_scroll = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("an exhausted two-post profile must not scroll")
    )
    host._human_tap_grid_thumbnail = lambda _target: (_ for _ in ()).throw(
        AssertionError("an exhausted grid must not reopen a post")
    )
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.post_navigation.time.sleep",
        lambda _seconds: None,
    )

    assert host._open_entry_post_of_profile(
        posts_count=2, username="kevin", reopening=True
    ) is False
