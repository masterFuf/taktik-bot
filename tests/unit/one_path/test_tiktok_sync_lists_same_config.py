"""One follow-graph sync config, one run: the desktop bridge and the CLI do the same thing with it.

The CLI had no id for this workflow (`tiktok.automation.sync_following`, `.sync_followers` and
`.sync_lists` were unknown): which list to read, the scroll and resolution budgets, the start and
the account the graph is recorded under were the bridge's alone.
"""
from dataclasses import asdict

import pytest

_BRIDGE_PROCESS_ONLY = {"force_stop tiktok"}


def _observed(rig):
    return {
        "configs": [asdict(config) for config in rig.built_configs],
        "calls": [call for call in rig.calls if call not in _BRIDGE_PROCESS_ONLY],
    }


def _run_both(rig, payload, workflow_id):
    bridge_exit = rig.run_bridge(payload)
    bridge = _observed(rig)
    rig.forget_run()

    result = rig.run_cli(payload, workflow_id=workflow_id)
    return bridge_exit, bridge, result, _observed(rig)


@pytest.mark.parametrize("list_type, workflow_id", [
    ("following", "tiktok.automation.sync_following"),
    ("followers", "tiktok.automation.sync_followers"),
    ("both", "tiktok.automation.sync_lists"),
])
def test_the_cli_reads_the_list_the_bridge_reads(rig, sync_payload, list_type, workflow_id):
    payload = sync_payload(list_type, maxScrolls=12, resolveMissingHandles=True, maxResolutions=4)
    _, bridge, result, cli = _run_both(rig, payload, workflow_id)

    assert result.exit_code == 0, result.output
    assert [c["list_type"] for c in cli["configs"]] == [list_type]
    assert cli["configs"] == bridge["configs"]
    assert cli["calls"] == bridge["calls"]
    assert cli["calls"][:3] == ["manager emulator-5554", "restart", "wait_app_surface"]
    assert "workflow_run as acting_account" in cli["calls"]


def test_the_cli_id_names_the_list_when_the_payload_does_not(rig, sync_payload):
    payload = sync_payload("followers")
    for key in ("workflowType", "listType"):
        payload.pop(key)

    result = rig.run_cli(payload, workflow_id="tiktok.automation.sync_followers")

    assert result.exit_code == 0, result.output
    assert [config.list_type for config in rig.built_configs] == ["followers"]


def test_without_an_account_neither_path_writes_a_graph(rig, sync_payload):
    rig.own_username = None
    bridge_exit, bridge, result, cli = _run_both(rig, sync_payload(), "tiktok.automation.sync_following")

    assert bridge_exit == 1
    assert result.exit_code == 1
    assert "SyncAccountUnknownError" in result.output
    assert bridge["configs"] == cli["configs"] == []
    assert cli["calls"] == bridge["calls"]


def test_a_sync_with_errors_fails_on_both_paths(rig, sync_payload):
    rig.sync_runs = [{"errors": 1, "completion_reason": "error"}, {"errors": 1, "completion_reason": "error"}]
    bridge_exit, bridge, result, cli = _run_both(rig, sync_payload(), "tiktok.automation.sync_following")

    assert bridge_exit == 1
    assert result.exit_code == 1
    assert "workflow_run as acting_account" in cli["calls"]
    assert cli["calls"] == bridge["calls"]
