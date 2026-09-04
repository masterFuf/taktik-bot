from taktik.core.social_media.tiktok.actions.atomic.scroll.scroll_actions import ScrollActions
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.workflow import ForYouWorkflow
from loguru import logger


def _actions(signatures):
    actions = ScrollActions.__new__(ScrollActions)
    actions.logger = logger
    actions.swipes = 0
    values = iter(signatures)
    actions._swipe_to_next_video = lambda: setattr(actions, "swipes", actions.swipes + 1)
    actions._current_video_signature = lambda: next(values)
    return actions


def test_changed_video_is_accepted_after_one_swipe(monkeypatch):
    monkeypatch.setattr("taktik.core.social_media.tiktok.actions.atomic.scroll.scroll_actions.time.sleep", lambda _n: None)
    actions = _actions(["next"])

    assert actions.scroll_to_next_video(previous_signature="current") is True
    assert actions.swipes == 1


def test_same_video_is_retried_once_and_then_accepted(monkeypatch):
    monkeypatch.setattr("taktik.core.social_media.tiktok.actions.atomic.scroll.scroll_actions.time.sleep", lambda _n: None)
    actions = _actions(["current", "next"])

    assert actions.scroll_to_next_video(previous_signature="current") is True
    assert actions.swipes == 2


def test_two_failed_swipes_report_failure_without_looping_forever(monkeypatch):
    monkeypatch.setattr("taktik.core.social_media.tiktok.actions.atomic.scroll.scroll_actions.time.sleep", lambda _n: None)
    actions = _actions(["current", "current"])

    assert actions.scroll_to_next_video(previous_signature="current") is False
    assert actions.swipes == 2


def test_for_you_advance_passes_the_current_video_identity_to_verification():
    class _Scroll:
        def __init__(self):
            self.previous = None

        def scroll_to_next_video(self, previous_signature=None):
            self.previous = previous_signature
            return True

    workflow = ForYouWorkflow.__new__(ForYouWorkflow)
    workflow.scroll = _Scroll()

    assert workflow._advance_to_next_video({"signature": "current"}) is True
    assert workflow.scroll.previous == "current"


def test_for_you_recovers_feed_when_snapshot_proves_current_surface_is_not_video():
    class _CachedSnapshotDevice:
        def __init__(self):
            self.clears = 0

        def clear_video_snapshot(self):
            self.clears += 1

    workflow = ForYouWorkflow.__new__(ForYouWorkflow)
    workflow.logger = logger
    workflow.detection = type("Detection", (), {"device": _CachedSnapshotDevice()})()
    forced = []
    workflow._ensure_on_for_you = lambda force_navigation=False: forced.append(force_navigation) or True

    assert workflow._recover_off_video_surface({"video_visible": False}) is True
    assert forced == [True]
    assert workflow.detection.device.clears == 1


def test_for_you_does_not_recover_when_video_visibility_is_unknown_or_true():
    workflow = ForYouWorkflow.__new__(ForYouWorkflow)

    assert workflow._recover_off_video_surface({"video_visible": True}) is False
    assert workflow._recover_off_video_surface({}) is False
