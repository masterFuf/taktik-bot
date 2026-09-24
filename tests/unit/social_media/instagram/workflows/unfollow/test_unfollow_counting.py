"""U5: every unfollow counts, in the session, the day and the warmup; the pause is a setting.

What it used to be: "Maximum d'unfollows" capped one BATCH, which the session relaunched until
its duration ran out (164 unfollows in a morning on one account); no ceiling (session, day,
warmup) counted unfollows; a batch that unfollowed nobody reported success, so the session looped
on it; the pause between two unfollows was a hardcoded 2 to 5 s whatever the settings said.
"""

from types import SimpleNamespace

import pytest

from fake_follow_list import FakeFacade, FakeScreen, follow_list_xml, walk_list
from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import UNFOLLOW_DEFAULTS
from taktik.core.social_media.instagram.actions.business.workflows.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.core.config_builder import build_instagram_automation_config
from taktik.core.social_media.instagram.workflows.core.workflow_runner import WorkflowRunner
from taktik.core.social_media.instagram.workflows.management.session.session import SessionManager


def _sm(warmup=None):
    settings = {} if warmup is None else {"warmup_policy": warmup}
    return SessionManager({"session_settings": settings})


# ── SessionManager ─────────────────────────────────────────────────────────────

def test_an_unfollow_is_counted_by_the_session():
    sm = _sm()
    sm.record_action("unfollow", success=True)
    sm.record_action("unfollow", success=False)
    assert sm.counters["unfollows"] == 1
    assert sm.counters["follows"] == 0


def test_the_session_maximum_is_a_real_ceiling():
    sm = _sm()
    assert sm.unfollow_allowance(3) == (3, None)
    for _ in range(3):
        sm.record_action("unfollow")
    room, reason = sm.unfollow_allowance(3)
    assert room == 0 and reason.code == "unfollows_cap"


def test_the_day_budget_of_the_warmup_is_its_own():
    sm = _sm(warmup={"max_unfollows_per_day": 10, "max_actions_per_day": 50})
    # 40 actions today (likes/follows/comments) do not spend the unfollow budget...
    sm.set_daily_usage_provider(lambda: {"total": 40, "unfollows": 7})
    assert sm.unfollow_allowance(50) == (3, None)
    # ...and a spent unfollow budget stops the unfollows with its own reason.
    sm.set_daily_usage_provider(lambda: {"total": 0, "unfollows": 10})
    room, reason = sm.unfollow_allowance(50)
    assert room == 0 and reason.code == "daily_unfollow_budget"


def test_no_ceiling_means_no_limit():
    assert _sm().unfollow_allowance(0) == (None, None)


# ── The pause between two unfollows ────────────────────────────────────────────

def test_defaults_follow_the_decisions_of_2026_09_23():
    assert UNFOLLOW_DEFAULTS["unfollow_delay_range"] == (2, 5)
    assert UNFOLLOW_DEFAULTS["bot_follows_only"] is True


def _config(unfollow=None, warmup=None):
    raw = {
        "deviceId": "x",
        "workflowType": "unfollow",
        "unfollow": unfollow or {},
        "session": {"durationMinutes": 30},
    }
    if warmup is not None:
        raw["warmupPolicy"] = warmup
    return build_instagram_automation_config(raw)


def _unfollow_action(config):
    return next(step for step in config["actions"] if step["type"] == "unfollow")


def test_the_pause_comes_from_the_settings():
    action = _unfollow_action(_config({"maxUnfollows": 12, "minDelay": 8, "maxDelay": 11}))
    assert (action["min_delay"], action["max_delay"]) == (8.0, 11.0)
    assert action["max_unfollows"] == 12


def test_the_pause_defaults_to_two_to_five_seconds():
    action = _unfollow_action(_config({"maxUnfollows": 12}))
    assert (action["min_delay"], action["max_delay"]) == (2.0, 5.0)


def test_the_warmup_unfollow_budget_reaches_the_bot():
    config = _config({"maxUnfollows": 12}, warmup={"maxUnfollowsPerDay": 25})
    assert config["session_settings"]["warmup_policy"]["max_unfollows_per_day"] == 25


@pytest.fixture
def _french_fast(monkeypatch):
    set_active_locale("fr")
    monkeypatch.setattr(UnfollowBusiness, "confirm_dialog_timeout", 0.0)
    monkeypatch.setattr(UnfollowBusiness, "row_state_timeout", 0.0)
    monkeypatch.setattr(unfollow_workflow.IPCEmitter, "emit_unfollow", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(unfollow_workflow.IPCEmitter, "emit_stats", staticmethod(lambda *a, **k: None))
    yield
    set_active_locale(None)


def test_the_loop_waits_the_configured_pause_and_counts_in_the_session(monkeypatch, _french_fast):
    pauses = []
    monkeypatch.setattr(unfollow_workflow.time, "sleep", lambda s: pauses.append(s))
    sm = _sm()
    screen = FakeScreen(follow_list_xml([("alice.fr", "Suivi(e)")]), follow_list_xml([("alice.fr", "Suivre")]))
    business = UnfollowBusiness(FakeFacade(screen), session_manager=sm)
    business._record_action = lambda *a, **k: None
    business._scroll_following_list = lambda: None
    business.nav_actions.problematic_page_detector = SimpleNamespace(is_action_blocked=lambda: False)

    stats = walk_list(business, {"max_unfollows": 1, "unfollow_delay_range": (7, 7)})

    assert stats["unfollows_made"] == 1
    assert sm.counters["unfollows"] == 1
    assert 7.0 in pauses


# ── The runner ─────────────────────────────────────────────────────────────────

def _runner(monkeypatch, batch_result, session_manager=None):
    finalized = []
    automation = SimpleNamespace(
        stats={}, session_finalized=False, session_manager=session_manager,
        helpers=SimpleNamespace(finalize_session=lambda status, reason: finalized.append(reason)),
    )
    runner = WorkflowRunner.__new__(WorkflowRunner)
    runner.automation = automation
    runner.logger = unfollow_workflow.logger
    seen_configs = []

    def run_batch(config):
        seen_configs.append(config)
        if session_manager is not None:
            for _ in range(batch_result.get("unfollows_made", 0)):
                session_manager.record_action("unfollow")
        return batch_result

    business = SimpleNamespace(
        sync_following_list=lambda *a, **k: {"new_count": 0, "updated_count": 0},
        scrape_non_followers_category=lambda *a, **k: {"non_followers_count": 0, "mutuals_count": 0},
        nav_actions=SimpleNamespace(navigate_to_profile_tab=lambda: True, open_following_list=lambda: True),
        run_unfollow_workflow=run_batch,
    )
    monkeypatch.setattr(runner, "_get_unfollow_business", lambda: business, raising=False)
    monkeypatch.setattr("time.sleep", lambda _s: None)
    return runner, finalized, seen_configs


def test_a_batch_without_unfollow_is_not_progress(monkeypatch):
    runner, finalized, _ = _runner(monkeypatch, {"unfollows_made": 0, "success": True, "stop_reason": None,
                                                 "candidates_left": 4})
    assert runner._run_unfollow_workflow({"type": "unfollow", "max_unfollows": 5}) is False
    assert finalized == []


def test_a_batch_that_only_refused_candidates_on_their_profile_is_progress(monkeypatch):
    runner, finalized, _ = _runner(monkeypatch, {"unfollows_made": 0, "success": True, "stop_reason": None,
                                                 "candidates_left": 4, "profile_refusals": {"verified": 2}})
    assert runner._run_unfollow_workflow({"type": "unfollow", "max_unfollows": 5}) is True
    assert finalized == []


def test_nobody_left_to_unfollow_ends_the_session_with_its_reason(monkeypatch):
    runner, finalized, _ = _runner(monkeypatch, {"unfollows_made": 2, "success": True, "stop_reason": None,
                                                 "candidates_left": 0, "refusals": {"whitelisted": 3}})
    assert runner._run_unfollow_workflow({"type": "unfollow", "max_unfollows": 5}) is False
    assert [r.code for r in finalized] == ["no_unfollow_candidates"]


def test_the_session_ends_when_its_maximum_is_reached(monkeypatch):
    sm = _sm()
    runner, finalized, configs = _runner(
        monkeypatch, {"unfollows_made": 3, "success": True, "stop_reason": None}, session_manager=sm)
    assert runner._run_unfollow_workflow({"type": "unfollow", "max_unfollows": 3}) is False
    assert configs[0]["max_unfollows"] == 3
    assert [r.code for r in finalized] == ["unfollows_cap"]


def test_a_second_batch_gets_only_what_is_left(monkeypatch):
    sm = _sm()
    sm.record_action("unfollow")
    sm.record_action("unfollow")
    runner, _finalized, configs = _runner(
        monkeypatch, {"unfollows_made": 1, "success": True, "stop_reason": None, "candidates_left": 5},
        session_manager=sm)
    assert runner._run_unfollow_workflow({"type": "unfollow", "max_unfollows": 5}) is True
    assert configs[0]["max_unfollows"] == 3


def test_a_spent_day_budget_stops_before_any_sync(monkeypatch):
    sm = _sm(warmup={"max_unfollows_per_day": 10})
    sm.set_daily_usage_provider(lambda: {"total": 0, "unfollows": 10})
    runner, finalized, configs = _runner(
        monkeypatch, {"unfollows_made": 1, "success": True, "stop_reason": None}, session_manager=sm)
    assert runner._run_unfollow_workflow({"type": "unfollow", "max_unfollows": 5}) is False
    assert configs == []
    assert [r.code for r in finalized] == ["daily_unfollow_budget"]


# ── The day's ACTION budget is not the unfollow's (review of 2026-09-24) ────────

def test_a_spent_action_budget_does_not_end_an_unfollow_session():
    sm = SessionManager({"session_settings": {"workflow_type": "unfollow",
                                              "warmup_policy": {"max_actions_per_day": 40}}})
    sm.set_daily_usage_provider(lambda: {"total": 40, "unfollows": 0})
    assert sm.should_continue() == (True, "")


def test_the_same_budget_still_ends_a_likes_session():
    sm = SessionManager({"session_settings": {"workflow_type": "feed",
                                              "warmup_policy": {"max_actions_per_day": 40}}})
    sm.set_daily_usage_provider(lambda: {"total": 40, "unfollows": 0})
    keep_going, reason = sm.should_continue()
    assert keep_going is False and reason.code == "daily_budget"


def test_an_unreadable_day_budget_stops_the_unfollow():
    sm = _sm(warmup={"max_unfollows_per_day": 10})

    def broken():
        raise RuntimeError("base locked")

    sm.set_daily_usage_provider(broken)
    reasons = [sm.unfollow_allowance(5)[1] for _ in range(5)]
    assert reasons[-1] is not None and reasons[-1].code == "daily_budget_unreadable"
