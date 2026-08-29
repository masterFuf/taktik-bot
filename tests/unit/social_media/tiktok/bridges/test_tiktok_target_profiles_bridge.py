"""The bridge reads the list it was sent, and refuses to invent one."""

from bridges.tiktok.workflows.automation.target_profiles import build_profile_list
from bridges.tiktok.workflows.runtime.dispatcher import dispatch_tiktok_workflow


def test_the_list_is_read_from_any_of_the_payload_shapes():
    assert build_profile_list({"profiles": ["@marie", "paul"]}) == ["marie", "paul"]
    assert build_profile_list({"targetProfiles": ["marie"]}) == ["marie"]
    assert build_profile_list({"usernames": [" marie "]}) == ["marie"]


def test_a_search_query_is_not_a_profile_list():
    """`build_target_list` falls back to `searchQuery`, which for the followers workflow means
    "the account whose followers we want". Reusing it here would turn a run launched without a
    list into a run against one arbitrary account."""
    assert build_profile_list({"searchQuery": "marie"}) == []
    assert build_profile_list({"targetAccounts": ["marie"]}) == []
    assert build_profile_list({}) == []


def test_empty_entries_never_become_a_target():
    assert build_profile_list({"profiles": ["", "  ", "@", "marie"]}) == ["marie"]


def test_the_workflow_type_is_dispatched():
    """Registered in the dispatcher, so a payload asking for it does not fall through to the
    unknown-workflow error."""
    calls = {}

    def _fake_runner(config):
        calls["config"] = config
        return True

    import bridges.tiktok.workflows.automation.target_profiles as module

    original = module.run_target_profiles_workflow
    module.run_target_profiles_workflow = _fake_runner
    try:
        ok, workflow_type = dispatch_tiktok_workflow(
            {"workflowType": "target_profiles", "deviceId": "abc", "profiles": ["marie"]}
        )
    finally:
        module.run_target_profiles_workflow = original

    assert ok is True
    assert workflow_type == "target_profiles"
    assert calls["config"]["profiles"] == ["marie"]
