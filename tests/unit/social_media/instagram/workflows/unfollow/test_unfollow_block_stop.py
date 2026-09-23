"""U4: the first sign of an action block stops the unfollow, and the session with it.

A "Try again later" used to stop nothing: the loop tapped the next row. The unfollow now asks
the same detector as the followers workflow (`is_action_blocked`) after every attempt, and hands
back `stop_reasons.action_blocked()`, which the runner turns into the end of the session.
"""

from types import SimpleNamespace

import pytest

from fake_follow_list import FakeFacade, FakeScreen, follow_list_xml
from taktik.core.social_media.instagram.actions.business.workflows.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.core.workflow_runner import WorkflowRunner
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons


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


class _Detector:
    def __init__(self, blocked_after):
        self.calls = 0
        self.blocked_after = blocked_after

    def is_action_blocked(self):
        self.calls += 1
        return self.calls >= self.blocked_after


def _business(detector, *screens):
    screen = FakeScreen(*screens)
    business = UnfollowBusiness(FakeFacade(screen))
    business._record_action = lambda *a, **k: None
    business._scroll_following_list = lambda: None
    business.nav_actions.problematic_page_detector = detector
    return business, screen


def test_the_loop_stops_at_the_first_block():
    rows_before = follow_list_xml([("alice.fr", "Suivi(e)"), ("bob_fr", "Suivi(e)")])
    rows_after = follow_list_xml([("alice.fr", "Suivre"), ("bob_fr", "Suivi(e)")])
    business, screen = _business(_Detector(blocked_after=1), rows_before, rows_after)

    stats = business.run_simple_unfollow_from_list({"max_unfollows": 5})

    assert stats["unfollows_made"] == 1
    assert stats["stop_reason"].code == "action_blocked"
    assert len(screen.taps) == 1  # bob_fr is never tapped


def test_a_block_after_an_unconfirmed_tap_stops_too():
    same = follow_list_xml([("alice.fr", "Suivi(e)"), ("bob_fr", "Suivi(e)")])
    business, screen = _business(_Detector(blocked_after=1), same, same)

    stats = business.run_simple_unfollow_from_list({"max_unfollows": 5})

    assert stats["unfollows_made"] == 0 and stats["unconfirmed"] == 1
    assert stats["stop_reason"].code == "action_blocked"
    assert len(screen.taps) == 1


def test_no_block_no_stop_reason():
    business, _screen = _business(
        _Detector(blocked_after=99),
        follow_list_xml([("alice.fr", "Suivi(e)")]),
        follow_list_xml([("alice.fr", "Suivre")]),
    )
    stats = business.run_simple_unfollow_from_list({"max_unfollows": 1})
    assert stats["unfollows_made"] == 1 and stats["stop_reason"] is None


def test_the_runner_ends_the_session_on_the_block(monkeypatch):
    finalized = []
    automation = SimpleNamespace(
        stats={},
        session_finalized=False,
        helpers=SimpleNamespace(finalize_session=lambda status, reason: finalized.append((status, reason))),
    )
    runner = WorkflowRunner.__new__(WorkflowRunner)
    runner.automation = automation
    runner.logger = unfollow_workflow.logger

    fake_business = SimpleNamespace(
        sync_following_list=lambda *a, **k: {"new_count": 0, "updated_count": 0},
        scrape_non_followers_category=lambda *a, **k: {"non_followers_count": 0, "mutuals_count": 0},
        nav_actions=SimpleNamespace(navigate_to_profile_tab=lambda: True, open_following_list=lambda: True),
        run_simple_unfollow_from_list=lambda config: {
            "unfollows_made": 2, "success": True, "stop_reason": stop_reasons.action_blocked()},
    )
    monkeypatch.setattr(runner, "_get_unfollow_business", lambda: fake_business, raising=False)
    monkeypatch.setattr("time.sleep", lambda _s: None)

    assert runner._run_unfollow_workflow({"type": "unfollow", "max_unfollows": 5}) is False
    assert finalized and finalized[0][1].code == "action_blocked"
    assert automation.stats["unfollows"] == 2


def test_should_stop_session_is_gone():
    """Decision 7 (2026-09-23): the first block stops the run; the 3-block rule had no caller."""
    assert not hasattr(ProblematicPageDetector, "should_stop_session")
