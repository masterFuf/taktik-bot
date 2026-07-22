from types import SimpleNamespace

from taktik.core.social_media.instagram.actions.atomic.interaction.story_interaction import (
    StoryInteractionMixin,
)
from taktik.core.social_media.instagram.actions.atomic.navigation.search_navigation import (
    SearchNavigationMixin,
)
from taktik.core.social_media.instagram.actions.atomic.story_state import (
    parse_story_position,
)
import taktik.core.social_media.instagram.actions.atomic.navigation.search_navigation as search_nav


_DECISION = {
    "style": "deliberate",
    "energy": 0.37,
    "distance_scale": 1.04,
    "velocity_scale": 0.90,
    "settle_scale": 1.15,
    "dwell_scale": 1.22,
}


class _BehaviorState:
    def __init__(self):
        self.calls = []

    def plan_directional_gesture(self, *, context, gesture):
        self.calls.append((context, gesture))
        return {"context": context, "gesture": gesture, **_DECISION}

    @staticmethod
    def snapshot():
        return {"style": "deliberate", "energy": 0.37, "gesture_count": 4}


class _SwipeDevice:
    def __init__(self, result=True):
        self.calls = []
        self.result = result

    def human_hswipe(self, direction, **kwargs):
        self.calls.append((direction, kwargs))
        return self.result


class _StoryTrayHost(StoryInteractionMixin):
    def __init__(self, swipe_result=True):
        self.behavior_state = _BehaviorState()
        self.device = _SwipeDevice(swipe_result)
        self.delays = []
        self.logger = SimpleNamespace(error=lambda *_a, **_k: None)

    @staticmethod
    def _tray_y_ratio(_selector, default_ratio):
        return default_ratio

    def _human_like_delay(self, action_type="general", scale=1.0):
        self.delays.append((action_type, scale))


def test_story_tray_hswipe_uses_session_motor_and_settle_scales():
    host = _StoryTrayHost()

    assert host.scroll_feed_stories_left() is True

    assert host.behavior_state.calls == [("story_feed_tray", "hswipe")]
    direction, kwargs = host.device.calls[0]
    assert direction == "left"
    assert kwargs["y_ratio"] == 0.17
    assert kwargs["distance_scale"] == 1.04
    assert kwargs["velocity_scale"] == 0.90
    assert host.delays == [("scroll", 1.15)]


def test_story_trays_propagate_a_physical_swipe_failure_without_settle_delay():
    for method_name in ("scroll_feed_stories_left", "scroll_highlights_left"):
        host = _StoryTrayHost(swipe_result=False)

        assert getattr(host, method_name)() is False
        assert host.delays == []


class _StoryAdvanceHost(SearchNavigationMixin):
    def __init__(self):
        self.behavior_state = _BehaviorState()
        self.swipes = []
        self.delays = []
        self.device = SimpleNamespace(
            info={"displayWidth": 1080, "displayHeight": 2280},
            human_tap=lambda _zone, quick=False: quick,
            human_hswipe=self._human_hswipe,
            click=lambda *_args: None,
        )
        self.detection_selectors = SimpleNamespace(story_viewer_indicators=("viewer",))
        self.logger = SimpleNamespace(
            debug=lambda *_a, **_k: None,
            error=lambda *_a, **_k: None,
        )

    @staticmethod
    def _first_interactive_sticker_bounds():
        return None

    @staticmethod
    def _wait_for_element(_selector, timeout=0):
        return timeout == 2

    def _human_hswipe(self, direction, **kwargs):
        self.swipes.append((direction, kwargs))
        return True

    def _human_like_delay(self, action_type="general", scale=1.0):
        self.delays.append((action_type, scale))


class _VerifiedStoryAdvanceHost(_StoryAdvanceHost):
    def __init__(self, signatures, *, viewer_present=True):
        super().__init__()
        self.signatures = list(signatures)
        self.viewer_present = viewer_present

    def _story_transition_signature(self):
        if len(self.signatures) > 1:
            return self.signatures.pop(0)
        return self.signatures[0] if self.signatures else None

    def _wait_for_element(self, _selector, timeout=0):
        return self.viewer_present and timeout == 2


def test_story_advance_tap_consumes_a_session_gesture():
    host = _StoryAdvanceHost()

    assert host.navigate_to_next_story() is True

    assert host.behavior_state.calls == [("story_advance", "tap")]
    assert host._last_behavior_gesture["settle_scale"] == 1.15
    assert host.delays == [("story_transition", 1.15)]


def test_story_previous_uses_production_horizontal_gesture_and_session_scales():
    host = _StoryAdvanceHost()

    assert host.navigate_to_previous_story() is True

    assert host.behavior_state.calls == [("story_previous", "hswipe")]
    assert host.swipes == [(
        "right",
        {"distance_scale": 1.04, "velocity_scale": 0.90},
    )]
    assert host.delays == [("story_transition", 1.15)]


def test_story_transition_signature_parses_english_and_french_positions():
    assert parse_story_position("Story 2 of 5") == (2, 5)
    assert parse_story_position("Story de friend, 3 sur 7, il y a 2 h") == (3, 7)
    assert parse_story_position("friend's story, 2 hours ago") is None


def test_story_transition_signature_uses_the_accessibility_position():
    host = _StoryAdvanceHost()
    node = SimpleNamespace(attrib={
        "resource-id": "com.instagram.android:id/reel_viewer_text_container",
        "content-desc": "Story de friend, 3 sur 7, il y a 2 h",
    })
    host.device.xpath = lambda _selector: SimpleNamespace(all=lambda: [node])

    reliable, value = host._story_transition_signature()

    assert reliable is True
    assert value[0] == ((3, 7),)


def test_story_advance_accepts_an_observed_slide_change(monkeypatch):
    before = (True, ("friend", 1, 3))
    after = (True, ("friend", 2, 3))
    host = _VerifiedStoryAdvanceHost([before, after])
    monkeypatch.setattr(search_nav.time, "sleep", lambda _seconds: None)

    assert host.navigate_to_next_story() is True
    assert host.delays == [("story_transition", 1.15)]


def test_story_advance_rejects_an_injected_but_ignored_tap(monkeypatch):
    unchanged = (True, ("friend", 1, 3))
    host = _VerifiedStoryAdvanceHost([unchanged])
    monkeypatch.setattr(search_nav.time, "sleep", lambda _seconds: None)

    assert host.navigate_to_next_story() is False
    assert host.delays == []


def test_story_advance_reports_a_closed_viewer_when_transition_is_inconclusive(monkeypatch):
    before = (True, ("friend", 3, 3))
    host = _VerifiedStoryAdvanceHost([before, None], viewer_present=False)
    monkeypatch.setattr(search_nav.time, "sleep", lambda _seconds: None)

    assert host.navigate_to_next_story() is False
    assert host.delays == []


def test_story_previous_rejects_an_injected_but_ignored_swipe(monkeypatch):
    unchanged = (True, ("friend", 2, 3))
    host = _VerifiedStoryAdvanceHost([unchanged])
    monkeypatch.setattr(search_nav.time, "sleep", lambda _seconds: None)

    assert host.navigate_to_previous_story() is False
    assert host.delays == []


def test_generic_post_pager_propagates_horizontal_swipe_failure(monkeypatch):
    host = _StoryAdvanceHost()
    monkeypatch.setattr(search_nav, "human_hswipe_raw", lambda *_a, **_k: False)

    assert host.navigate_to_next_post() is False

    assert host.behavior_state.calls == [("generic_post_pager", "hswipe")]
    assert host.delays == []
