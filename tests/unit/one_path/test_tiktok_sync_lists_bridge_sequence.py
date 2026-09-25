"""The desktop's follow-graph sync, frozen: what the bridge asks of the phone and what it prints.

The snapshot beside this file was recorded from the bridge while it still read its payload itself,
before the run moved into the Agent handler. Same device calls, same stdout events in the same
order, same config, same exit code.
"""
import json
from dataclasses import asdict
from pathlib import Path

import pytest

SNAPSHOT = json.loads(
    (Path(__file__).parent / "tiktok_sync_lists_bridge_sequence.json").read_text(encoding="utf-8")
)


def scheduler_payload():
    """What scheduler-tiktok-runner.ts sends for a Sync Followers node, with the node's defaults."""
    return {
        "deviceId": "emulator-5554", "workflowType": "sync_followers", "listType": "followers",
        "incremental": True, "maxScrolls": 100, "resolveMissingHandles": False, "maxResolutions": 25,
        "minDelay": 1, "maxDelay": 3,
    }


def _without(payload, *keys):
    for key in keys:
        payload.pop(key, None)
    return payload


def scenario(name, sync_payload):
    """(payload, sync run outcomes, acting account) of one recorded run."""
    runs, account = [], "acting_account"
    if name == "sync_following_page":
        payload = sync_payload()
    elif name == "sync_followers_page":
        payload = sync_payload("followers", resolveMissingHandles=True, maxResolutions=5, incremental=False)
    elif name == "sync_lists_page":
        payload = sync_payload("both")
        runs = [{"rows_seen": 3, "new_count": 2, "updated_count": 1, "unidentified": 2,
                 "following_seen": 2, "followers_seen": 1, "reciprocal_seen": 1}]
    elif name == "sync_scheduler_node":
        payload = scheduler_payload()
    elif name == "sync_list_type_wins":
        payload = sync_payload("following", listType="both")
    elif name == "sync_workflow_type_only":
        payload = _without(sync_payload("followers"), "listType")
    elif name == "sync_list_type_garbage":
        payload = sync_payload("both", listType="garbage")
    elif name == "sync_account_from_app":
        payload = sync_payload(botUsername="from_app")
        account = None
    elif name == "sync_account_unknown":
        payload = sync_payload()
        account = None
    elif name == "sync_with_errors":
        payload = sync_payload()
        runs = [{"errors": 1, "completion_reason": "error"}]
    elif name == "sync_no_device":
        payload = _without(sync_payload(), "deviceId")
    else:
        raise KeyError(name)
    return payload, runs, account


SCENARIOS = (
    "sync_following_page", "sync_followers_page", "sync_lists_page", "sync_scheduler_node",
    "sync_list_type_wins", "sync_workflow_type_only", "sync_list_type_garbage",
    "sync_account_from_app", "sync_account_unknown", "sync_with_errors", "sync_no_device",
)


def observe(rig, name, sync_payload):
    payload, runs, account = scenario(name, sync_payload)
    rig.sync_runs = list(runs)
    rig.own_username = account
    code = rig.run_bridge(payload)
    # JSON round trip: the snapshot holds what went over the wire, not Python types.
    return json.loads(json.dumps({
        "exit": code,
        "calls": rig.calls,
        "events": [[kind, event] for kind, event in rig.events],
        "configs": [asdict(config) for config in rig.built_configs],
    }))


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_bridge_runs_exactly_as_recorded(rig, sync_payload, name):
    assert name in SNAPSHOT, f"no recording for {name}"
    observed = observe(rig, name, sync_payload)
    expected = SNAPSHOT[name]

    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["configs"] == expected["configs"]
    assert observed["exit"] == expected["exit"]


def test_every_recording_is_a_scenario():
    assert sorted(SNAPSHOT) == sorted(SCENARIOS)


def test_the_workflow_is_the_one_a_stop_signal_reaches(rig, sync_payload):
    from bridges.common.runtime import signal_handler

    rig.run_bridge(sync_payload())
    assert signal_handler._workflow is rig.workflows[-1]
