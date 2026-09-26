"""The session's duration ends the unfollow walk, not only the list reads and the batches.

The Unfollow page shows "Durée de session" as the cap that ends a cleanup. The bot checked it
while reading the lists and between two batches, never while walking the list: a batch went on to
its maximum past the end of the session, one unfollow cycle (profile check, tap, pause) per row.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from fake_follow_list import FakeFacade, FakeScreen, follow_list_xml, walk_list
from taktik.core.social_media.instagram.actions.business.workflows.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.core.workflow_runner import WorkflowRunner
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons
from taktik.core.social_media.instagram.workflows.management.session.session import SessionManager


@pytest.fixture(autouse=True)
def _french_and_fast(monkeypatch):
    set_active_locale("fr")
    monkeypatch.setattr(unfollow_workflow.time, "sleep", lambda _s: None)
    monkeypatch.setattr(UnfollowBusiness, "confirm_dialog_timeout", 0.0)
    monkeypatch.setattr(UnfollowBusiness, "row_state_timeout", 0.0)
    monkeypatch.setattr(unfollow_workflow.IPCEmitter, "emit_unfollow", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(unfollow_workflow.IPCEmitter, "emit_stats", staticmethod(lambda *a, **k: None))
    yield
    set_active_locale(None)


def _unfollow_session(minutes: int, started_minutes_ago: float) -> SessionManager:
    sm = SessionManager({"session_settings": {"workflow_type": "unfollow", "session_duration_minutes": minutes}})
    sm.session_start_time = datetime.now() - timedelta(minutes=started_minutes_ago)
    return sm


def _business(session_manager, *screens):
    screen = FakeScreen(*screens)
    business = UnfollowBusiness(FakeFacade(screen), session_manager=session_manager)
    recorded = []
    business._record_action = lambda username, action, count=1: recorded.append(username)
    business._scroll_following_list = lambda: None
    business.nav_actions.problematic_page_detector = SimpleNamespace(is_action_blocked=lambda: False)
    return business, screen, recorded


def test_a_session_past_its_duration_taps_no_row():
    rows = follow_list_xml([("a1", "Suivi(e)"), ("a2", "Suivi(e)"), ("a3", "Suivi(e)")])
    business, screen, recorded = _business(_unfollow_session(minutes=5, started_minutes_ago=6), rows)

    stats = walk_list(business, {"max_unfollows": 3})

    assert screen.taps == [] and recorded == []
    assert stats["stop_reason"].code == "duration_cap"


def test_the_duration_reached_during_the_walk_ends_it_after_the_unfollow_under_way():
    before = follow_list_xml([("a1", "Suivi(e)"), ("a2", "Suivi(e)"), ("a3", "Suivi(e)")])
    after1 = follow_list_xml([("a1", "Suivre"), ("a2", "Suivi(e)"), ("a3", "Suivi(e)")])
    checks = []

    def should_continue():
        # Within the duration for the first row, past it from the second one on.
        checks.append(1)
        if len(checks) == 1:
            return True, ""
        return False, stop_reasons.duration_cap(5)

    session = SimpleNamespace(should_continue=should_continue, record_action=lambda *a, **k: None)
    business, screen, recorded = _business(session, before, after1)

    stats = walk_list(business, {"max_unfollows": 3})

    assert recorded == ["a1"] and len(screen.taps) == 1
    assert stats["unfollows_made"] == 1
    assert stats["stop_reason"].code == "duration_cap"


def test_a_session_within_its_duration_walks_to_its_maximum():
    before = follow_list_xml([("a1", "Suivi(e)"), ("a2", "Suivi(e)")])
    after1 = follow_list_xml([("a1", "Suivre"), ("a2", "Suivi(e)")])
    after2 = follow_list_xml([("a1", "Suivre"), ("a2", "Suivre")])
    business, _screen, recorded = _business(_unfollow_session(minutes=60, started_minutes_ago=1),
                                            before, after1, after2)

    stats = walk_list(business, {"max_unfollows": 2})

    assert recorded == ["a1", "a2"] and stats["stop_reason"] is None


def test_the_runner_ends_the_session_with_the_duration_reason(monkeypatch):
    finalized = []
    runner = WorkflowRunner.__new__(WorkflowRunner)
    runner.automation = SimpleNamespace(
        stats={}, session_finalized=False, session_manager=None,
        helpers=SimpleNamespace(finalize_session=lambda status, reason: finalized.append((status, reason))),
    )
    runner.logger = unfollow_workflow.logger
    engine = SimpleNamespace(run_unfollow_workflow=lambda cfg: {
        "unfollows_made": 1, "success": True, "candidates_left": 4,
        "stop_reason": stop_reasons.duration_cap(5)})
    monkeypatch.setattr(runner, "_get_unfollow_business", lambda: engine, raising=False)

    assert runner._run_unfollow_workflow({"type": "unfollow", "max_unfollows": 5}) is False
    assert [(status, reason.code) for status, reason in finalized] == [("COMPLETED", "duration_cap")]
