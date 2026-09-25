"""The list a Target Profiles run was sent is read as sent, and never invented."""

from bridges.tiktok.workflows.runtime.dispatcher import dispatch_tiktok_workflow
from taktik.core.social_media.tiktok.actions.business.workflows.target_profiles.payload import (
    target_profiles_from_payload,
)


def test_the_list_is_read_from_any_of_the_payload_shapes():
    assert target_profiles_from_payload({"profiles": ["@marie", "paul"]}) == ["marie", "paul"]
    assert target_profiles_from_payload({"targetProfiles": ["marie"]}) == ["marie"]
    assert target_profiles_from_payload({"usernames": [" marie "]}) == ["marie"]


def test_a_search_query_is_not_a_profile_list():
    """The followers reading falls back to `searchQuery`, which for the followers workflow means
    "the account whose followers we want". Reusing it here would turn a run launched without a
    list into a run against one arbitrary account."""
    assert target_profiles_from_payload({"searchQuery": "marie"}) == []
    assert target_profiles_from_payload({"targetAccounts": ["marie"]}) == []
    assert target_profiles_from_payload({}) == []


def test_empty_entries_never_become_a_target():
    assert target_profiles_from_payload({"profiles": ["", "  ", "@", "marie"]}) == ["marie"]


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
