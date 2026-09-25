"""The desktop's TikTok cold DM, frozen: what the bridge asks of the phone, what it prints, the AI
calls it makes and what it writes.

The snapshot beside this file was recorded from `dm_outreach_bridge` while the reading of the
payload, the duplicate guard, the sent-DM recorder, the AI generation and the stdin entry still
lived in the bridge, before they moved into the core and onto `run_bridge_main`. The cold-DM
workflow is the real one; only its phone (TikTok manager, navigation, Message button, privacy
probes, composer), its pauses and its random picks are fakes. Same device calls, same stdout
events in the same order, same AI calls, same rows handed to the database.

Three recordings changed on purpose, and keep the old code's values beside the new ones
(`calls_old_code`, `events_old_code`): a run without a recipient and a manual run without a
message are refused before the phone is touched (the old bridge connected, then the workflow
refused), and an empty stdin reports the shared entrypoint's words. The app sends none of the
three: the page and the scheduler refuse an empty recipient list and a manual run without a
message, and the main process always writes the payload.
"""
import json
from pathlib import Path

import pytest

SNAPSHOT = json.loads(
    (Path(__file__).parent / "tiktok_dm_outreach_bridge_sequence.json").read_text(encoding="utf-8")
)


def _without(payload, *keys):
    for key in keys:
        payload.pop(key, None)
    return payload


def scenario(name, rig, outreach_payload):
    """The stdin of one recorded run; the phone and the database are set on `rig`."""
    rig.install_dm_database()
    rig.use_real_outreach()
    if name == "page_manual":
        rig.already_dmed = {"fan_two"}
        rig.privacy_blocked = {"fan_three"}
        return outreach_payload()
    if name == "page_ai":
        return outreach_payload("ai", recipients=["fan_one", "fan_two"])
    if name == "page_ai_generation_fails":
        rig.ai_text_fails = True
        return outreach_payload("ai", recipients=["fan_one"])
    if name == "page_ai_without_key":
        return _without(outreach_payload("ai"), "openrouterApiKey")
    if name == "scheduler_node":
        return outreach_payload(recipients=["fan_one", "fan_two"], delayMin=3, delayMax=8, maxDms=1,
                                accountId=1)
    if name == "all_already_sent":
        rig.already_dmed = {"fan_one", "fan_two", "fan_three"}
        return outreach_payload()
    if name == "recipient_failures":
        rig.unreachable_profiles = {"fan_one"}
        rig.no_message_button = {"fan_two"}
        rig.cold_send_failures = {"fan_three"}
        return outreach_payload()
    if name == "connect_fails":
        rig.outreach_connects = False
        return outreach_payload()
    if name == "no_device":
        return _without(outreach_payload(), "device_id")
    if name == "no_recipients":
        return outreach_payload(recipients=[])
    if name == "manual_without_message":
        return outreach_payload(messages=[])
    if name == "empty_stdin":
        return ""
    if name == "invalid_json":
        return "{not json\n"
    raise KeyError(name)


SCENARIOS = (
    "page_manual", "page_ai", "page_ai_generation_fails", "page_ai_without_key", "scheduler_node",
    "all_already_sent", "recipient_failures", "connect_fails", "no_device", "no_recipients",
    "manual_without_message", "empty_stdin", "invalid_json",
)


def observe(rig, name, outreach_payload):
    code = rig.run_outreach_bridge(scenario(name, rig, outreach_payload))
    # JSON round trip: the snapshot holds what went over the wire, not Python types.
    return json.loads(json.dumps({
        "exit": code,
        "calls": rig.calls,
        "events": [[kind, event] for kind, event in rig.events],
        "ai_services": rig.ai_services,
        "db_writes": rig.db_writes,
    }))


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_bridge_runs_exactly_as_recorded(rig, outreach_payload, name):
    assert name in SNAPSHOT, f"no recording for {name}"
    observed = observe(rig, name, outreach_payload)
    expected = SNAPSHOT[name]

    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["ai_services"] == expected["ai_services"]
    assert observed["db_writes"] == expected["db_writes"]
    assert observed["exit"] == expected["exit"]


def test_every_recording_is_a_scenario():
    assert sorted(SNAPSHOT) == sorted(SCENARIOS)


def test_a_request_with_nothing_to_send_is_refused_before_the_phone_is_touched():
    changed = {name: record for name, record in SNAPSHOT.items() if "calls_old_code" in record}
    assert sorted(changed) == ["manual_without_message", "no_recipients"]
    for name, record in changed.items():
        assert record["calls"] == [], name
        assert record["calls_old_code"][:2] == ["outreach_manager emulator-5554", "outreach_connect"], name
        assert record["events"][-1][0] == "error", name
        assert record["exit"] == record["exit_old_code"] == 1, name
        assert record["db_writes"] == [], name


def test_an_empty_stdin_reports_the_shared_entrypoint_words():
    record = SNAPSHOT["empty_stdin"]
    assert record["events_old_code"] == [["error", {"error": "No configuration received"}]]
    assert record["events"] == [["error", {"error": "No config received from stdin"}]]
    assert record["calls"] == [] and record["exit"] == 1
