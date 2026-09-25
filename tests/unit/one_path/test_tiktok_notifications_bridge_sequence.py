"""The desktop's TikTok notifications pass, frozen: what the bridge asks of the phone, what it
prints and what it writes.

The snapshot beside this file was recorded from the bridge while the pass still lived in it,
before it moved into the core. Same device calls, same stdout events in the same order, same rows
handed to the database.

One field was re-recorded on purpose: `exit`. The old runner returned a process exit code (0 on
success) where the dispatcher expects a success flag, so a pass that succeeded exited 1 (the app
closed it as ERROR and filed a crash report) and a pass that failed exited 0. The old code's value
stays in the snapshot as `exit_old_code`.
"""
import json
from pathlib import Path

import pytest

SNAPSHOT = json.loads(
    (Path(__file__).parent / "tiktok_notifications_bridge_sequence.json").read_text(encoding="utf-8")
)


def _without(payload, *keys):
    for key in keys:
        payload.pop(key, None)
    return payload


def scenario(name, rig, notifications_payload):
    """The payload of one recorded run; the phone is set on `rig`."""
    rig.show_notifications()
    if name == "notifications_page":
        return notifications_payload()
    if name == "notifications_every_step":
        rig.hello_candidates = ["Ana", "Bob", "Cid"]
        rig.suggestion_reads = [[], [], [{"name": "Suggested A"}, {"name": "Suggested B"}]]
        return notifications_payload(maxFollowerResolutions=1, maxActivityRows=1, maxHellos=2,
                                     maxSuggestedFollows=1)
    if name == "notifications_nothing_asked":
        return notifications_payload(scanNewFollowers=False, readActivity=False)
    if name == "notifications_page_closed":
        rig.new_followers_page_opens = False
        return notifications_payload()
    if name == "notifications_no_new_follower":
        rig.new_follower_rows = []
        return notifications_payload()
    if name == "notifications_inbox_closed":
        rig.inbox_opens = False
        return notifications_payload(maxHellos=1, maxSuggestedFollows=1)
    if name == "notifications_activity_closed":
        rig.activity_opens = False
        return notifications_payload(maxSuggestedFollows=1)
    if name == "notifications_no_suggestion":
        return notifications_payload(readActivity=False, maxSuggestedFollows=2)
    if name == "notifications_step_fails":
        rig.activity_fails = True
        return notifications_payload()
    if name == "notifications_account_unread":
        rig.own_username = None
        return notifications_payload()
    if name == "notifications_start_fails":
        rig.restart_ok = False
        return notifications_payload()
    if name == "notifications_device_id_snake":
        return _without(notifications_payload(device_id="emulator-5554"), "deviceId")
    raise KeyError(name)


SCENARIOS = (
    "notifications_page", "notifications_every_step", "notifications_nothing_asked",
    "notifications_page_closed", "notifications_no_new_follower", "notifications_inbox_closed",
    "notifications_activity_closed", "notifications_no_suggestion", "notifications_step_fails",
    "notifications_account_unread", "notifications_start_fails", "notifications_device_id_snake",
)


def observe(rig, name, notifications_payload):
    code = rig.run_bridge(scenario(name, rig, notifications_payload))
    # JSON round trip: the snapshot holds what went over the wire, not Python types.
    return json.loads(json.dumps({
        "exit": code,
        "calls": rig.calls,
        "events": [[kind, event] for kind, event in rig.events],
        "db_writes": rig.db_writes,
    }))


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_bridge_runs_exactly_as_recorded(rig, notifications_payload, name):
    assert name in SNAPSHOT, f"no recording for {name}"
    observed = observe(rig, name, notifications_payload)
    expected = SNAPSHOT[name]

    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["db_writes"] == expected["db_writes"]
    assert observed["exit"] == expected["exit"]


def test_every_recording_is_a_scenario():
    assert sorted(SNAPSHOT) == sorted(SCENARIOS)


def test_the_exit_code_says_whether_the_pass_succeeded():
    for name, record in SNAPSHOT.items():
        kind, event = record["events"][-1]
        succeeded = kind == "notifications_result" and event["success"] is True
        assert record["exit"] == (0 if succeeded else 1), name
