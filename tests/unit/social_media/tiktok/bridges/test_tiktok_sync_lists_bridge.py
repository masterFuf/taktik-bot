"""One runner, two workflow types — and it has to know which list it was asked for."""

from bridges.tiktok.workflows.automation.sync_lists import resolve_list_type
from bridges.tiktok.workflows.runtime.dispatcher import dispatch_tiktok_workflow


def test_the_workflow_type_says_which_list():
    assert resolve_list_type({"workflowType": "sync_following"}) == "following"
    assert resolve_list_type({"workflowType": "sync_followers"}) == "followers"
    assert resolve_list_type({"workflowType": "sync_lists"}) == "both"


def test_an_explicit_list_type_wins():
    assert resolve_list_type({"workflowType": "sync_following", "listType": "both"}) == "both"
    assert resolve_list_type({"workflowType": "sync_followers", "listType": "following"}) == "following"


def test_an_unknown_payload_reads_the_following_list_rather_than_guessing_both():
    """Defaulting to 'both' would double the device time of a mislabelled run."""
    assert resolve_list_type({}) == "following"
    assert resolve_list_type({"workflowType": "nonsense"}) == "following"
    assert resolve_list_type({"listType": "garbage"}) == "following"


def test_all_three_types_are_dispatched():
    calls = []

    def _fake_runner(config):
        calls.append(config.get("workflowType"))
        return True

    import bridges.tiktok.workflows.automation.sync_lists as module

    original = module.run_sync_lists_workflow
    module.run_sync_lists_workflow = _fake_runner
    try:
        for workflow_type in ("sync_following", "sync_followers", "sync_lists"):
            ok, dispatched = dispatch_tiktok_workflow(
                {"workflowType": workflow_type, "deviceId": "abc"}
            )
            assert ok is True
            assert dispatched == workflow_type
    finally:
        module.run_sync_lists_workflow = original

    assert calls == ["sync_following", "sync_followers", "sync_lists"]
