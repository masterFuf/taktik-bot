"""The desktop's TikTok inbox flows, frozen: new followers (list, follow-back, AI welcome pass),
unreplied conversations, message requests and activity. What the bridge asks of the phone, what it
prints, the config it builds, the AI services it opens and what it writes.

The snapshot beside this file was recorded from the bridges while the four flows and the welcome
pass still lived in them, before they moved into the core.

Two scenarios were re-recorded on purpose: a follow-back with no name and an `execute` with no
decision. The old bridges restarted TikTok, went through the whole startup, and only then refused;
the refusal now comes first, with the same error and the same exit code, and the phone is not
touched. The old code's values stay in the snapshot (`calls_old_code`, `events_old_code`,
`configs_old_code`). The app never sends either request: both buttons are disabled on an empty
selection.

Every welcome scenario but one sends through a stand-in of the cold-DM workflow.
`new_followers_welcome_no_message_entry` runs the production one: a follower whose profile offers
no message entry is skipped, and the bridge prints what the cold DM prints for it.
"""
import dataclasses
import json
from pathlib import Path

import pytest

SNAPSHOT = json.loads(
    (Path(__file__).parent / "tiktok_inbox_bridge_sequence.json").read_text(encoding="utf-8")
)


def _without(payload, *keys):
    for key in keys:
        payload.pop(key, None)
    return payload


def _welcome(rig, inbox_payload, welcome_ai, **block):
    ai = welcome_ai()
    ai["newFollowers"].update(block)
    return inbox_payload("new_followers", ai=ai)


def scenario(name, rig, inbox_payload, welcome_ai):
    """The payload of one recorded run; the phone and the database are set on `rig`."""
    rig.install_dm_database()
    rig.show_welcome_verdicts()
    rig.show_inbox_lists()
    if name == "new_followers_page":
        return inbox_payload("new_followers")
    if name == "new_followers_empty":
        rig.new_follower_rows = []
        return _welcome(rig, inbox_payload, welcome_ai)
    if name == "new_followers_ai_without_welcome_block":
        return inbox_payload("new_followers", ai={"enabled": True, "openrouterApiKey": "test-openrouter-key"})
    if name == "new_followers_welcome_no_ai_key":
        ai = welcome_ai()
        ai.pop("openrouterApiKey")
        return inbox_payload("new_followers", ai=ai)
    if name == "new_followers_welcome":
        rig.already_dmed = {"fan_two"}
        return _welcome(rig, inbox_payload, welcome_ai)
    if name == "new_followers_welcome_thread_exists":
        rig.threads_with_us = {"fan_one"}
        return _welcome(rig, inbox_payload, welcome_ai)
    if name == "new_followers_welcome_guard_broken":
        rig.guard_broken = True
        return _welcome(rig, inbox_payload, welcome_ai)
    if name == "new_followers_welcome_no_message":
        return _welcome(rig, inbox_payload, welcome_ai, messages=[])
    if name == "new_followers_welcome_account_unread":
        rig.own_username = None
        return _welcome(rig, inbox_payload, welcome_ai)
    if name == "new_followers_welcome_send_fails":
        rig.welcome_send_failures = {"fan_one"}
        return _welcome(rig, inbox_payload, welcome_ai)
    if name == "new_followers_welcome_no_message_entry":
        rig.use_real_outreach()
        rig.no_message_button = {"fan_two"}
        return _welcome(rig, inbox_payload, welcome_ai)
    if name == "new_followers_welcome_without_follow_back":
        return _welcome(rig, inbox_payload, welcome_ai, followBack=False)
    if name == "new_followers_welcome_follow_back_only":
        return _welcome(rig, inbox_payload, welcome_ai, welcomeDm=False)
    if name == "new_followers_follow_back_page":
        rig.follow_back_failures = {"Fan Two"}
        return inbox_payload("new_followers", mode="follow_back")
    if name == "new_followers_follow_back_empty":
        return inbox_payload("new_followers", mode="follow_back", usernames=[])
    if name == "new_followers_no_device":
        return _without(inbox_payload("new_followers"), "deviceId")
    if name == "new_followers_start_fails":
        rig.restart_ok = False
        return inbox_payload("new_followers")
    if name == "unreplied_page":
        return inbox_payload("dm_unreplied")
    if name == "unreplied_every_conversation":
        return inbox_payload("dm_unreplied", onlyUnreplied=False, maxItems=5)
    if name == "unreplied_no_device":
        return _without(inbox_payload("dm_unreplied"), "deviceId")
    if name == "unreplied_start_fails":
        rig.restart_ok = False
        return inbox_payload("dm_unreplied")
    if name == "requests_scrape_page":
        return inbox_payload("dm_requests")
    if name == "requests_execute_page":
        return inbox_payload("dm_requests", mode="execute")
    if name == "requests_execute_empty":
        return inbox_payload("dm_requests", mode="execute", decisions=[])
    if name == "requests_start_fails":
        rig.restart_ok = False
        return inbox_payload("dm_requests")
    if name == "activity_page":
        return inbox_payload("dm_activity")
    if name == "activity_no_device":
        return _without(inbox_payload("dm_activity"), "deviceId")
    if name == "activity_start_fails":
        rig.restart_ok = False
        return inbox_payload("dm_activity")
    raise KeyError(name)


SCENARIOS = (
    "new_followers_page", "new_followers_empty", "new_followers_ai_without_welcome_block",
    "new_followers_welcome_no_ai_key", "new_followers_welcome", "new_followers_welcome_thread_exists",
    "new_followers_welcome_guard_broken", "new_followers_welcome_no_message",
    "new_followers_welcome_account_unread", "new_followers_welcome_send_fails",
    "new_followers_welcome_no_message_entry", "new_followers_welcome_without_follow_back",
    "new_followers_welcome_follow_back_only",
    "new_followers_follow_back_page", "new_followers_follow_back_empty", "new_followers_no_device",
    "new_followers_start_fails", "unreplied_page", "unreplied_every_conversation", "unreplied_no_device",
    "unreplied_start_fails", "requests_scrape_page", "requests_execute_page", "requests_execute_empty",
    "requests_start_fails", "activity_page", "activity_no_device", "activity_start_fails",
)


def observe(rig, name, inbox_payload, welcome_ai):
    code = rig.run_bridge(scenario(name, rig, inbox_payload, welcome_ai))
    # JSON round trip: the snapshot holds what went over the wire, not Python types.
    return json.loads(json.dumps({
        "exit": code,
        "calls": rig.calls,
        "events": [[kind, event] for kind, event in rig.events],
        "configs": [dataclasses.asdict(config) for config in rig.built_configs],
        "ai_services": rig.ai_services,
        "db_writes": rig.db_writes,
    }))


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_bridge_runs_exactly_as_recorded(rig, inbox_payload, welcome_ai, name):
    assert name in SNAPSHOT, f"no recording for {name}"
    observed = observe(rig, name, inbox_payload, welcome_ai)
    expected = SNAPSHOT[name]

    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["configs"] == expected["configs"]
    assert observed["ai_services"] == expected["ai_services"]
    assert observed["db_writes"] == expected["db_writes"]
    assert observed["exit"] == expected["exit"]


def test_every_recording_is_a_scenario():
    assert sorted(SNAPSHOT) == sorted(SCENARIOS)


def test_a_request_with_nothing_to_act_on_is_refused_before_the_phone_is_touched():
    changed = {name: record for name, record in SNAPSHOT.items() if "calls_old_code" in record}
    assert sorted(changed) == ["new_followers_follow_back_empty", "requests_execute_empty"]
    for name, record in changed.items():
        assert record["calls"] == ["force_stop tiktok"], name
        assert record["events"] == [record["events_old_code"][-1]], name
        assert record["events"][-1][0] == "error", name
        assert record["exit"] == 1, name


def test_the_welcome_dm_skips_a_follower_without_message_entry_as_the_cold_dm_does():
    record = SNAPSHOT["new_followers_welcome_no_message_entry"]
    results = {event["username"]: event for kind, event in record["events"] if kind == "dm_result"}
    assert results["fan_one"] == {"error": None, "success": True, "username": "fan_one"}
    assert results["fan_two"] == {
        "error": "No message entry on profile", "reason": "no_message_entry", "skipped": True,
        "success": False, "username": "fan_two",
    }
    stats = [event["stats"] for kind, event in record["events"] if kind == "stats"]
    assert stats[-1] == {"failed": 0, "no_message_entry": 1, "not_found": 0, "privacy_blocked": 0,
                         "sent": 1, "success": 1}
    # Not marked: the entry comes back once we follow them.
    marked = [write["sent_dm"]["recipient"] for write in record["db_writes"] if "sent_dm" in write]
    assert marked == ["fan_one"]
