"""A run asked to stop ends the profile it was on STOPPED, never as an error.

The profile pipeline filed the stop (`run_halt`) as `ERROR_INTERACTION` (« run stop requested »): the
followers and likers loops counted it an error of the run and went back to their list before seeing
the latch, a gesture after the stop (Kevin's decision of 2026-11-16: a stop makes no gesture). A
profile the engine left on the latch with nothing done was marked processed as « left by the draw »,
lost for a later run. The pipeline now settles the stop itself: whatever the profile came to, the
latch up at its end makes it STOPPED, an outcome of its own (`was_stopped`, never `was_error`).
"""

import types

import pytest

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.base.base_business import profile_processing
from taktik.core.social_media.instagram.actions.base.base_business.profile_processing import (
    ProfileProcessingMixin,
    ProfileProcessingResult,
)


class _Logger:
    def info(self, *a, **k): pass
    def debug(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def success(self, *a, **k): pass


class _Stats:
    def increment(self, *a, **k): pass


@pytest.fixture
def pipeline(monkeypatch):
    """The real pipeline; the screen reads, the filters and the base are the stand-ins."""
    marked, steps = [], []
    monkeypatch.setattr(profile_processing.IPCEmitter, "emit_profile_visit", lambda *a, **k: None)
    monkeypatch.setattr(profile_processing.InstagramWorkflowStateService, "mark_profile_as_processed",
                        lambda *a, **k: marked.append(a))
    monkeypatch.setattr(profile_processing, "emit_step", lambda *a, **k: steps.append(k))

    class _Processor(ProfileProcessingMixin):
        pass

    processor = _Processor()
    processor.logger = _Logger()
    processor.stats_manager = _Stats()
    processor.profile_business = types.SimpleNamespace(
        get_complete_profile_info=lambda **k: {"is_private": False, "followers_count": 10})
    processor.filtering_business = types.SimpleNamespace(
        apply_comprehensive_filter=lambda *a, **k: {"suitable": True})
    processor._relationship_skip_reason = lambda *a, **k: None
    processor._perform_interactions_on_profile = lambda *a, **k: {"actually_interacted": False}
    processor.marked = marked
    processor.steps = steps
    return processor


def test_a_stop_seen_before_the_engine_is_stopped_not_an_error(pipeline):
    def _extract(**k):
        run_halt.demander_arret(run_halt.NETWORK_LOST, "test")
        return {"is_private": False, "followers_count": 10}

    pipeline.profile_business.get_complete_profile_info = _extract

    result = pipeline._process_profile_on_screen("alice", {}, source_type="FOLLOWER")

    assert result.status == ProfileProcessingResult.STOPPED
    assert result.was_stopped and not result.was_error
    assert pipeline.marked == []


def test_a_profile_the_engine_left_on_the_latch_with_nothing_done_is_not_lost(pipeline):
    def _engine(*a, **k):
        run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")
        return {"actually_interacted": False}

    pipeline._perform_interactions_on_profile = _engine

    result = pipeline._process_profile_on_screen("alice", {}, source_type="FOLLOWER")

    assert result.status == ProfileProcessingResult.STOPPED
    assert pipeline.marked == [], "nothing was done on it: a later run takes it again"


def test_a_profile_acted_on_before_the_stop_stays_recorded(pipeline):
    def _engine(*a, **k):
        run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")
        return {"actually_interacted": True, "likes": 1}

    pipeline._perform_interactions_on_profile = _engine

    result = pipeline._process_profile_on_screen("alice", {}, source_type="FOLLOWER")

    assert result.status == ProfileProcessingResult.STOPPED
    assert len(pipeline.marked) == 1, "its like landed: no later run likes it again"


def test_a_navigation_that_failed_on_a_lost_network_is_stopped(pipeline):
    def _navigate(username):
        run_halt.demander_arret(run_halt.NETWORK_LOST, "test")
        return False

    pipeline.nav_actions = types.SimpleNamespace(navigate_to_profile=_navigate)

    result = pipeline._process_profile_on_screen("alice", {}, source_type="SELECTION",
                                                 navigate_if_needed=True)

    assert result.was_stopped and not result.was_error


def test_the_heartbeat_says_the_profile_was_stopped(pipeline):
    def _extract(**k):
        run_halt.demander_arret(run_halt.NETWORK_LOST, "test")
        return {"is_private": False, "followers_count": 10}

    pipeline.profile_business.get_complete_profile_info = _extract

    pipeline._process_profile_on_screen("alice", {}, source_type="FOLLOWER")

    done = [step for step in pipeline.steps if step.get("action") == "done"]
    assert [step["outcome"] for step in done] == ["stopped"]


def test_without_a_stop_an_interaction_failure_is_still_an_error(pipeline):
    pipeline._perform_interactions_on_profile = lambda *a, **k: {
        "actually_interacted": False, "technical_failure": True, "failure_stage": "post_entry"}

    result = pipeline._process_profile_on_screen("alice", {}, source_type="FOLLOWER")

    assert result.status == ProfileProcessingResult.ERROR_INTERACTION and result.was_error
