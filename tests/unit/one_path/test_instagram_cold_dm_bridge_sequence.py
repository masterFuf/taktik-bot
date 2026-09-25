"""The desktop's Instagram cold DM, frozen: what the bridge asks of the phone, writes and prints.

The snapshot beside this file was recorded from `cold_dm_bridge` while its workflow still lived in
the bridge, before it moved into the core as the one cold DM engine (the CLI had a second one).
Moving code must not move a gesture: same selector queries and taps, same text typed, same rows in
`sent_dms`, same AI calls, same stdout (progress lines and the final JSON), same exit code. Set
TAKTIK_RECORD_SNAPSHOT=1 to record it again, on purpose only.
"""
import json
import os
from pathlib import Path

import pytest

from instagram_cold_dm_rig import AI_KEY, cold_dm_payload

SNAPSHOT_PATH = Path(__file__).parent / "instagram_cold_dm_bridge_sequence.json"
RECORD = os.environ.get("TAKTIK_RECORD_SNAPSHOT") == "1"
SNAPSHOT = {} if RECORD else json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _observed(rig, code) -> dict:
    config_path = str(rig.tmp_path / "cold_dm_config.json")
    observed = {
        "exit": code,
        "calls": rig.calls,
        "stdout": rig.stdout_lines,
        "events": [[kind, payload] for kind, payload in rig.events],
        "db": rig.db,
        "ai": rig.ai_calls,
    }
    text = json.dumps(observed, default=str).replace(json.dumps(config_path)[1:-1], "<config>")
    return json.loads(text)


def _check(name, rig, code) -> None:
    observed = _observed(rig, code)
    if RECORD:
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8")) if SNAPSHOT_PATH.exists() else {}
        snapshot[name] = observed
        SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    expected = SNAPSHOT[name]
    assert observed["calls"] == expected["calls"]
    assert observed["db"] == expected["db"]
    assert observed["ai"] == expected["ai"]
    assert observed["stdout"] == expected["stdout"]
    assert observed["events"] == expected["events"]
    assert observed["exit"] == expected["exit"]


def test_a_public_profile_gets_its_dm_and_a_private_one_is_skipped(igc_rig):
    _check("default", igc_rig, igc_rig.run_bridge(cold_dm_payload()))


def test_a_private_profile_with_a_message_button_is_tried_when_allowed(igc_rig):
    igc_rig.users["closed_one"] = {"private": True, "message_button": True}
    _check("private_allowed", igc_rig, igc_rig.run_bridge(cold_dm_payload(skipPrivateAccounts=False)))


def test_a_private_profile_without_a_button_is_a_skip_of_its_own(igc_rig):
    _check("private_no_button", igc_rig, igc_rig.run_bridge(cold_dm_payload(skipPrivateAccounts=False)))


def test_a_certified_profile_is_skipped_when_asked(igc_rig):
    igc_rig.users["open_one"] = {"verified": True}
    _check("verified_skipped", igc_rig, igc_rig.run_bridge(cold_dm_payload(skipVerifiedAccounts=True)))


def test_recipients_already_reached_are_not_contacted_again(igc_rig):
    igc_rig.already_dmed = {"open_one", "closed_one"}
    _check("all_done", igc_rig, igc_rig.run_bridge(cold_dm_payload()))


def test_an_ai_run_writes_each_message(igc_rig):
    payload = cold_dm_payload(messageMode="ai", aiPrompt="Invite them to the tasting", messages=[],
                              openrouterApiKey=AI_KEY, recipients=["open_one"])
    _check("ai", igc_rig, igc_rig.run_bridge(payload))


def test_a_recipient_the_search_does_not_find_is_a_failure(igc_rig):
    igc_rig.users["open_one"] = {"found": False}
    _check("not_found", igc_rig, igc_rig.run_bridge(cold_dm_payload(recipients=["open_one"])))


def test_a_public_profile_without_a_message_button_is_a_failure(igc_rig):
    igc_rig.users["open_one"] = {"message_button": False}
    _check("no_button", igc_rig, igc_rig.run_bridge(cold_dm_payload(recipients=["open_one"])))


def test_an_invite_already_sent_is_marked_done(igc_rig):
    igc_rig.users["open_one"] = {"invite_sent": True}
    _check("invite_sent", igc_rig, igc_rig.run_bridge(cold_dm_payload(recipients=["open_one"])))


def test_a_clone_is_restarted_on_its_package(igc_rig):
    _check("clone", igc_rig, igc_rig.run_bridge(cold_dm_payload(packageName="com.taktik.ig1",
                                                                  recipients=["open_one"])))


def test_the_session_cap_stops_the_run(igc_rig):
    _check("cap", igc_rig, igc_rig.run_bridge(cold_dm_payload(maxDmsPerSession=1,
                                                                recipients=["open_one", "open_two"])))


@pytest.mark.parametrize("name, overrides", [
    ("no_recipients", {"recipients": []}),
    ("no_messages", {"messages": []}),
])
def test_a_run_with_nothing_to_send_says_so(igc_rig, name, overrides):
    _check(name, igc_rig, igc_rig.run_bridge(cold_dm_payload(**overrides)))


def test_a_device_that_does_not_connect_stops_the_run(igc_rig):
    igc_rig.connect_ok = False
    _check("no_connection", igc_rig, igc_rig.run_bridge(cold_dm_payload()))


def test_a_payload_without_device_is_refused(igc_rig):
    payload = cold_dm_payload()
    del payload["deviceId"]
    _check("no_device", igc_rig, igc_rig.run_bridge(payload))


def test_no_config_file_is_refused(igc_rig):
    _check("no_argument", igc_rig, igc_rig.run_bridge(None, argv=["cold_dm_bridge"]))


def test_an_unreadable_config_is_refused(igc_rig):
    _check("unreadable", igc_rig, igc_rig.run_bridge("{not json"))
