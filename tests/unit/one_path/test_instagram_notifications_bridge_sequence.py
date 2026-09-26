"""The desktop's Instagram notifications bridge, frozen: what it asks, records and prints.

The snapshot beside this file was recorded from `notifications_bridge` while the desktop started
it with positional arguments and flags (`scan <device> <scroll> --account <u> --package <p>`...).
The bridge now reads one config file, as the DM bridge does: none of that may move a gesture.
Same calls to the phone and the workflow, same rows recorded, same stdout, same exit code, for
each of its nine commands. Set TAKTIK_RECORD_SNAPSHOT=1 to record it again, on purpose only.
"""
import json
import os
from pathlib import Path

from instagram_notifications_rig import BOT, CLONE, notif_command

SNAPSHOT_PATH = Path(__file__).parent / "instagram_notifications_bridge_sequence.json"
RECORD = os.environ.get("TAKTIK_RECORD_SNAPSHOT") == "1"
SNAPSHOT = {} if RECORD else json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

_BATCH = [
    {"action": "follow_actor", "username": "engaged_one"},
    {"action": "welcome_dm", "username": "new_fan", "text": "Welcome!"},
    {"action": "like", "username": "fan_one", "notif_type": "comment", "notif_text": "nice", "notif_time": "2h"},
    {"action": "like", "username": "fan_done", "notif_type": "comment", "notif_text": "done", "notif_time": "3h"},
    {"action": "reply", "username": "fan_two", "text": "Thanks a lot"},
    {"action": "follow_back", "username": "fan_three"},
    {"action": "follow_back", "username": "fan_four"},
    {"action": "welcome_dm", "username": "old_friend", "text": "Hi"},
    {"action": "follow_actor", "username": "already_followed"},
    {"action": "accept", "username": "req_one"},
    {"action": "ignore", "username": "req_two"},
    {"action": "shrug", "username": "someone"},
]


def _observed(rig, code) -> dict:
    return json.loads(json.dumps({"exit": code, "calls": rig.calls, "stdout": rig.stdout_lines}, default=str))


def _check(name, rig, code) -> None:
    observed = _observed(rig, code)
    if RECORD:
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8")) if SNAPSHOT_PATH.exists() else {}
        snapshot[name] = observed
        SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    expected = SNAPSHOT[name]
    assert observed["calls"] == expected["calls"]
    assert observed["stdout"] == expected["stdout"]
    assert observed["exit"] == expected["exit"]


def test_a_scan_restarts_reads_our_profile_records_and_closes(ign_rig):
    _check("scan", ign_rig, ign_rig.run_bridge(notif_command("scan", scroll=3, accountUsername=BOT)))


def test_a_scan_without_an_account_files_it_under_the_profile_read(ign_rig):
    _check("scan_no_account", ign_rig, ign_rig.run_bridge(notif_command("scan", scroll=0, packageName=CLONE)))


def test_a_scan_that_visits_suggestions_qualifies_them(ign_rig):
    _check("scan_suggestions", ign_rig, ign_rig.run_bridge(notif_command(
        "scan", scroll=2, accountUsername=BOT, followSuggestions=2,
        ai={"enabled": True, "profileAnalysis": True}, language="fr")))


def test_a_scan_whose_workflow_breaks_reports_it(ign_rig):
    ign_rig.raise_on = "scan"
    _check("scan_raises", ign_rig, ign_rig.run_bridge(notif_command("scan", scroll=3, accountUsername=BOT)))


def test_a_device_that_does_not_connect_stops_the_scan(ign_rig):
    ign_rig.connect_ok = False
    _check("scan_no_connection", ign_rig, ign_rig.run_bridge(notif_command("scan", scroll=3, accountUsername=BOT)))


def test_the_follow_requests_are_listed(ign_rig):
    _check("list_requests", ign_rig, ign_rig.run_bridge(notif_command("list_requests", limit=20, packageName=CLONE)))


def test_a_request_is_accepted_and_recorded(ign_rig):
    _check("accept", ign_rig, ign_rig.run_bridge(notif_command("accept", username="req_one", accountUsername=BOT)))


def test_a_request_is_ignored_and_recorded(ign_rig):
    _check("ignore", ign_rig, ign_rig.run_bridge(notif_command("ignore", username="req_two", accountUsername=BOT,
                                                               packageName=CLONE)))


def test_every_request_is_accepted(ign_rig):
    ign_rig.results["accept_all_requests"] = {"success": True, "count": 2, "accepted": ["req_one", "req_two"],
                                              "message": "2 accepted"}
    _check("accept_all", ign_rig, ign_rig.run_bridge(notif_command("accept_all", max=10, accountUsername=BOT)))


def test_a_reply_is_sent_and_recorded(ign_rig):
    _check("reply", ign_rig, ign_rig.run_bridge(notif_command("reply", username="fan_two", text="Thanks a lot",
                                                              accountUsername=BOT)))


def test_an_empty_reply_only_opens_the_field(ign_rig):
    _check("reply_empty", ign_rig, ign_rig.run_bridge(notif_command("reply", username="fan_two", text="",
                                                                    accountUsername=BOT)))


def test_a_comment_is_liked_and_recorded(ign_rig):
    _check("like", ign_rig, ign_rig.run_bridge(notif_command("like", username="fan_one", accountUsername=BOT)))


def test_a_follower_is_followed_back_and_recorded(ign_rig):
    _check("follow_back", ign_rig, ign_rig.run_bridge(notif_command("follow_back", username="fan_three",
                                                                    accountUsername=BOT)))


def test_a_batch_runs_in_one_session_with_its_caps(ign_rig):
    _check("batch", ign_rig, ign_rig.run_bridge(notif_command(
        "batch", actions=_BATCH, accountUsername=BOT, source="autopilot", followBackDailyCap=2,
        welcomeDmDailyCap=5, followActorDailyCap=3, packageName=CLONE)))


def test_a_batch_without_caps_nor_account(ign_rig):
    _check("batch_plain", ign_rig, ign_rig.run_bridge(notif_command(
        "batch", actions=[{"action": "like", "username": "fan_one"}, {"action": "reply", "username": "fan_two"}])))


def test_a_batch_stops_at_the_first_action_block(ign_rig):
    ign_rig.block_after = {"fan_one"}
    _check("batch_blocked", ign_rig, ign_rig.run_bridge(notif_command(
        "batch", actions=[{"action": "like", "username": "fan_one"}, {"action": "like", "username": "fan_two"},
                          {"action": "follow_back", "username": "fan_three"}], accountUsername=BOT)))


def test_an_unknown_command_is_refused(ign_rig):
    _check("unknown", ign_rig, ign_rig.run_bridge(notif_command("dance", username="x")))
