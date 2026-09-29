"""The TikTok dispatcher runs no workflow under a name that is not its own.

`target` was read by the bridge as the followers workflow while the scheduler and the CLI meant the
account search; no emitter sent it, and the id `tiktok.automation.target` is gone from the manifest
(the search is `search`). `scraping` has its own bridge, `tiktok_scraping_bridge`, and its id
`tiktok.standalone.tiktok_scraping`. A hand-written config naming either is refused instead of
running another workflow.
"""

import pytest

import bridges.tiktok.automation.dispatcher as dispatcher


@pytest.mark.parametrize("workflow_type", ["target", "scraping"])
def test_a_retired_name_is_refused_instead_of_running_a_workflow(monkeypatch, workflow_type):
    monkeypatch.setattr(dispatcher, "send_error", lambda *a, **k: None)
    with pytest.raises(dispatcher.UnknownWorkflowError):
        dispatcher.dispatch_tiktok_workflow({"workflowType": workflow_type})


def test_followers_still_runs_followers(monkeypatch):
    import bridges.tiktok.automation.followers as followers

    monkeypatch.setattr(followers, "run_followers_workflow", lambda config: True)
    assert dispatcher.dispatch_tiktok_workflow({"workflowType": "followers"}) == (True, "followers")
