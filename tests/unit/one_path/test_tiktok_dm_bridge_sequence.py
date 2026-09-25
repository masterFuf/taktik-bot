"""The desktop's TikTok DM read and send, frozen: what the bridge asks of the phone, what it prints,
the config it builds and what it writes.

The snapshot beside this file was recorded from the bridge while the reading, the run and the DM
persistence still lived in it, before they moved into the core. Same device calls, same stdout
events in the same order, same workflow config, same rows handed to the database.
"""
import dataclasses
import json
from pathlib import Path

import pytest

SNAPSHOT = json.loads(
    (Path(__file__).parent / "tiktok_dm_bridge_sequence.json").read_text(encoding="utf-8")
)


def _without(payload, *keys):
    for key in keys:
        payload.pop(key, None)
    return payload


def scenario(name, rig, dm_read_payload, dm_send_payload):
    """The payload of one recorded run; the phone and the database are set on `rig`."""
    rig.install_dm_database()
    rig.show_dm_inbox()
    if name == "dm_read_page":
        return dm_read_payload()
    if name == "dm_read_scheduler_node":
        return dm_read_payload(maxConversations=1, skipGroups=True, onlyUnread=True,
                               delayBetweenConversations=2)
    if name == "dm_read_empty_inbox":
        rig.dm_conversations = []
        return dm_read_payload()
    if name == "dm_read_account_unread":
        rig.own_username = None
        return dm_read_payload()
    if name == "dm_read_no_device":
        return _without(dm_read_payload(), "deviceId")
    if name == "dm_read_start_fails":
        rig.restart_ok = False
        return dm_read_payload()
    if name == "dm_send_page":
        rig.dm_send_failures = {"Fan Two"}
        return dm_send_payload()
    if name == "dm_send_all_sent":
        return dm_send_payload()
    if name == "dm_send_scheduler_node":
        return dm_send_payload(messages=[{"conversation": "fan_one", "message": "Hello"}],
                               delayBetweenMessages=1, delayAfterSend=0.5)
    if name == "dm_send_no_message":
        return dm_send_payload(messages=[])
    if name == "dm_send_no_device":
        return _without(dm_send_payload(), "deviceId")
    if name == "dm_send_account_unread":
        rig.own_username = None
        return dm_send_payload()
    if name == "dm_send_start_fails":
        rig.restart_ok = False
        return dm_send_payload()
    raise KeyError(name)


SCENARIOS = (
    "dm_read_page", "dm_read_scheduler_node", "dm_read_empty_inbox", "dm_read_account_unread",
    "dm_read_no_device", "dm_read_start_fails", "dm_send_page", "dm_send_all_sent",
    "dm_send_scheduler_node", "dm_send_no_message", "dm_send_no_device", "dm_send_account_unread",
    "dm_send_start_fails",
)


def observe(rig, name, dm_read_payload, dm_send_payload):
    code = rig.run_bridge(scenario(name, rig, dm_read_payload, dm_send_payload))
    # JSON round trip: the snapshot holds what went over the wire, not Python types.
    return json.loads(json.dumps({
        "exit": code,
        "calls": rig.calls,
        "events": [[kind, event] for kind, event in rig.events],
        "configs": [dataclasses.asdict(config) for config in rig.built_configs],
        "db_writes": rig.db_writes,
    }))


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_bridge_runs_exactly_as_recorded(rig, dm_read_payload, dm_send_payload, name):
    assert name in SNAPSHOT, f"no recording for {name}"
    observed = observe(rig, name, dm_read_payload, dm_send_payload)
    expected = SNAPSHOT[name]

    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["configs"] == expected["configs"]
    assert observed["db_writes"] == expected["db_writes"]
    assert observed["exit"] == expected["exit"]


def test_every_recording_is_a_scenario():
    assert sorted(SNAPSHOT) == sorted(SCENARIOS)
