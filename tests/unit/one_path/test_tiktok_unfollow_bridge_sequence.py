"""The desktop's TikTok unfollow, frozen: what the bridge asks of the phone, what it prints and the
config it builds.

The snapshot beside this file was recorded from `tiktok_unfollow_bridge` while the startup, the
choice of the acting account and the live callbacks still lived in the bridge, and while it read
its own stdin, before they moved into the core launcher and onto `run_bridge_main`. Same device
calls, same stdout events in the same order, same workflow config, same exit code.
"""
import dataclasses
import json
from pathlib import Path

import pytest

SNAPSHOT = json.loads(
    (Path(__file__).parent / "tiktok_unfollow_bridge_sequence.json").read_text(encoding="utf-8")
)


def scenario(name, rig, unfollow_payload):
    """The stdin of one recorded run; the phone is set on `rig`."""
    if name == "page":
        return unfollow_payload()
    if name == "scheduler_node":
        return unfollow_payload("scheduler_node")
    if name == "account_unread":
        rig.own_username = None
        return unfollow_payload("scheduler_node")
    if name == "account_named_in_payload":
        return unfollow_payload(botUsername="@other_account")
    if name == "start_fails":
        rig.restart_ok = False
        return unfollow_payload()
    if name == "workflow_fails":
        rig.unfollow_fails = True
        return unfollow_payload()
    if name == "no_device":
        payload = unfollow_payload()
        payload.pop("device_id")
        return payload
    if name == "empty_stdin":
        return ""
    if name == "invalid_json":
        return "{not json\n"
    raise KeyError(name)


SCENARIOS = (
    "page", "scheduler_node", "account_unread", "account_named_in_payload", "start_fails",
    "workflow_fails", "no_device", "empty_stdin", "invalid_json",
)


def observe(rig, name, unfollow_payload):
    code = rig.run_unfollow_bridge(scenario(name, rig, unfollow_payload))
    # JSON round trip: the snapshot holds what went over the wire, not Python types.
    return json.loads(json.dumps({
        "exit": code,
        "calls": rig.calls,
        "events": [[kind, event] for kind, event in rig.events],
        "configs": [dataclasses.asdict(config) for config in rig.built_configs],
    }))


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_bridge_runs_exactly_as_recorded(rig, unfollow_payload, name):
    assert name in SNAPSHOT, f"no recording for {name}"
    observed = observe(rig, name, unfollow_payload)
    expected = SNAPSHOT[name]

    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["configs"] == expected["configs"]
    assert observed["exit"] == expected["exit"]


def test_every_recording_is_a_scenario():
    assert sorted(SNAPSHOT) == sorted(SCENARIOS)
