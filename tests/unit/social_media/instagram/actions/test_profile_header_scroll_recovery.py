"""Regressions for bounded profile-header recovery around deferred interactions."""

from types import SimpleNamespace

from taktik.core.social_media.instagram.actions.atomic.scroll.base_scroll import (
    BaseScrollMixin,
)
from taktik.core.social_media.instagram.actions.core.base_business.popup_handling import (
    PopupHandlingMixin,
)
from taktik.core.social_media.instagram.ui.selectors.shell.popups import PopupSelectors


class _Logger:
    def __init__(self):
        self.messages = []

    def debug(self, message):
        self.messages.append(str(message))


class _ScrollHarness:
    def __init__(self):
        self.logger = _Logger()
        self.gestures = []
        self.sleeps = []

    def _human_swipe(self, **kwargs):
        self.gestures.append(("swipe", kwargs))
        return True

    def _strong_flick(self, **kwargs):
        self.gestures.append(("flick", kwargs))
        return True

    def _random_sleep(self, low, high):
        self.sleeps.append((low, high))


def test_scroll_to_top_does_not_gesture_when_target_is_already_visible():
    harness = _ScrollHarness()

    reached = BaseScrollMixin.scroll_to_top(
        harness,
        max_attempts=6,
        stop_condition=lambda: True,
    )

    assert reached is True
    assert harness.gestures == []
    assert harness.sleeps == []


def test_scroll_to_top_stops_after_first_gesture_that_reveals_target():
    harness = _ScrollHarness()

    reached = BaseScrollMixin.scroll_to_top(
        harness,
        max_attempts=6,
        stop_condition=lambda: len(harness.gestures) >= 1,
    )

    assert reached is True
    assert len(harness.gestures) == 1
    assert len(harness.sleeps) == 1


def test_scroll_to_top_reports_unreached_target_after_bounded_attempts():
    harness = _ScrollHarness()

    reached = BaseScrollMixin.scroll_to_top(
        harness,
        max_attempts=3,
        stop_condition=lambda: False,
    )

    assert reached is False
    assert len(harness.gestures) == 3


class _XPath:
    def __init__(self, exists):
        self.exists = exists


class _SuggestionsDevice:
    def __init__(self, visible_selector):
        self.visible_selector = visible_selector
        self.scroll_calls = []

    def xpath(self, selector):
        return _XPath(selector == self.visible_selector)

    def human_scroll(self, *args, **kwargs):
        self.scroll_calls.append((args, kwargs))


class _PopupHarness:
    def __init__(self, selector):
        self.logger = _Logger()
        self.popup_selectors = SimpleNamespace(
            follow_suggestions_indicators=[selector],
        )
        self.device = _SuggestionsDevice(selector)


def test_inline_follow_suggestions_are_observed_without_scrolling():
    selector = '//android.widget.TextView[contains(@text, "Suggestions")]'
    harness = _PopupHarness(selector)

    detected = PopupHandlingMixin._handle_follow_suggestions_popup(harness)

    assert detected is True
    assert harness.device.scroll_calls == []


def test_follow_suggestion_detection_excludes_broad_suggested_matches():
    selectors = PopupSelectors()

    assert not any(
        'resource-id, "suggested"' in selector
        or 'content-desc, "Suggested"' in selector
        for selector in selectors.follow_suggestions_indicators
    )
