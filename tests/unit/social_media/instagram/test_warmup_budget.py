"""The warmup budget reads the day of the account a run acts for, from the ledger.

`WarmupBudget` is the counter the automation (`SessionManager.warmup`) and the Taktik Agent share;
the checks themselves are held by `test_session_warmup.py` and by the Agent's bridge run
(`tests/unit/app/contract/test_workflow_contract_taktik_agent.py`). Here: where the day comes from.
"""

import taktik.core.social_media.instagram.workflows.management.session.warmup_budget as warmup_budget
from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation
from taktik.core.social_media.instagram.workflows.management.session.warmup_budget import (
    WarmupBudget,
    warmup_policy_from_payload,
)


def _earlier_likes(db, count):
    """An account with `count` likes filed today, as a run files them."""
    account_id, _ = db.get_or_create_account("acting", is_bot=True)
    for index in range(count):
        assert db.record_interaction(account_id, f"liked_{index}", "LIKE")
    return account_id


def test_the_automation_counts_against_the_day_of_its_active_account(db, monkeypatch):
    """Before the account is known the day is empty; once it is, the day's likes stop the run."""
    monkeypatch.setattr(warmup_budget, "get_db_service", lambda: db)
    account_id = _earlier_likes(db, 3)
    automation = InstagramAutomation.__new__(InstagramAutomation)
    automation.logger = warmup_budget.log
    automation.config = {"session_settings": {"warmup_policy": {"max_actions_per_day": 3}}}
    automation.active_account_id = None
    automation.update_session_manager_config()

    assert automation.session_manager.should_continue() == (True, "")

    automation.active_account_id = account_id
    running, reason = automation.session_manager.should_continue()

    assert running is False
    assert reason.code == "daily_budget"


def test_no_account_yet_means_no_read_of_the_ledger(monkeypatch):
    """The day of an unknown account is empty, not a failed read counted toward the stop."""

    def no_base():
        raise AssertionError("the ledger is read without an account")

    monkeypatch.setattr(warmup_budget, "get_db_service", no_base)
    budget = WarmupBudget({"max_actions_per_day": 3})
    budget.count_against_account(lambda: None)

    assert budget.read_daily_usage() == {}
    assert budget.daily_usage_failures == 0


def test_the_file_caps_are_read_by_one_reader():
    """The desktop's names in, the budget's names out; 0 for an axis the file leaves out."""
    caps = warmup_policy_from_payload({"maxActionsPerDay": 50, "minActionGapSeconds": 45, "maxFollowsPerDay": None})

    assert caps == {
        "max_actions_per_day": 50,
        "max_follows_per_day": 0,
        "max_comments_per_day": 0,
        "max_unfollows_per_day": 0,
        "min_action_gap_seconds": 45.0,
        "max_actions_per_session": 0,
    }
    assert warmup_policy_from_payload(None) is None
    assert warmup_policy_from_payload("50") is None


def test_actions_left_is_the_tighter_of_the_day_and_the_run():
    budget = WarmupBudget({"max_actions_per_day": 50, "max_actions_per_session": 25})
    budget.set_daily_usage_provider(lambda: {"total": 40})

    assert budget.actions_left(session_actions=0) == 10
    assert budget.actions_left(session_actions=20) == 5
    assert budget.actions_left(session_actions=30) == 0
    assert WarmupBudget({}).actions_left(session_actions=30) is None
