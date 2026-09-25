"""`target` no longer reaches the followers workflow through the bridge.

The scheduler node "target accounts" and the CLI id `tiktok.automation.target` both run the search;
only the bridge read `workflowType: target` as the followers workflow. No emitter sent it, so the
alias is gone: a hand-written config naming it is refused instead of running another workflow.
"""

import pytest

import bridges.tiktok.workflows.runtime.dispatcher as dispatcher


def test_target_is_refused_instead_of_running_followers(monkeypatch):
    monkeypatch.setattr(dispatcher, "send_error", lambda *a, **k: None)
    with pytest.raises(dispatcher.UnknownWorkflowError):
        dispatcher.dispatch_tiktok_workflow({"workflowType": "target"})


def test_followers_still_runs_followers(monkeypatch):
    import bridges.tiktok.workflows.automation.followers as followers

    monkeypatch.setattr(followers, "run_followers_workflow", lambda config: True)
    assert dispatcher.dispatch_tiktok_workflow({"workflowType": "followers"}) == (True, "followers")
