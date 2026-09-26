"""The desktop's Instagram DM bridge, frozen: what it asks of the phone, writes and prints.

The snapshot beside this file was recorded from `dm_bridge` while its runtime still lived in the
bridge and the desktop started it with positional arguments (`read <device> <limit>`,
`send <device> <username> <message>`). The runtime moved into the core, the bridge reads a config
file: none of that may move a gesture. Same queries and taps, same rows written, same stdout (the
conversation events and the final JSON), same exit code. Set TAKTIK_RECORD_SNAPSHOT=1 to record it
again, on purpose only.
"""
import json
import os
from pathlib import Path

from instagram_dm_rig import CLONE, dm_command

SNAPSHOT_PATH = Path(__file__).parent / "instagram_dm_bridge_sequence.json"
RECORD = os.environ.get("TAKTIK_RECORD_SNAPSHOT") == "1"
SNAPSHOT = {} if RECORD else json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _observed(rig, code) -> dict:
    return json.loads(json.dumps({"exit": code, "calls": rig.calls, "stdout": rig.stdout_lines, "db": rig.db},
                                 default=str))


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
    assert observed["stdout"] == expected["stdout"]
    assert observed["exit"] == expected["exit"]


def test_a_read_emits_each_conversation_and_records_them(igd_rig):
    _check("read", igd_rig, igd_rig.run_bridge(dm_command("read")))


def test_a_read_whose_inbox_header_is_unreadable_visits_our_profile(igd_rig):
    igd_rig.header_readable = False
    _check("read_profile_fallback", igd_rig, igd_rig.run_bridge(dm_command("read")))


def test_a_read_with_a_limit_stops_there(igd_rig):
    _check("read_limit", igd_rig, igd_rig.run_bridge(dm_command("read", limit=1)))


def test_a_read_on_a_clone_restarts_the_clone(igd_rig):
    _check("read_clone", igd_rig, igd_rig.run_bridge(dm_command("read", packageName=CLONE)))


def test_a_read_that_cannot_reach_the_inbox_fails(igd_rig):
    igd_rig.inbox_ok = False
    _check("read_no_inbox", igd_rig, igd_rig.run_bridge(dm_command("read")))


def test_a_read_that_raises_reports_it(igd_rig):
    igd_rig.raise_on_inbox = True
    _check("read_raises", igd_rig, igd_rig.run_bridge(dm_command("read")))


def test_a_device_that_does_not_connect_stops_the_read(igd_rig):
    igd_rig.connect_ok = False
    _check("read_no_connection", igd_rig, igd_rig.run_bridge(dm_command("read")))


def test_the_requests_folder_is_read_like_the_inbox(igd_rig):
    _check("requests", igd_rig, igd_rig.run_bridge(dm_command("read_requests")))


def test_no_requests_folder_is_an_empty_result(igd_rig):
    igd_rig.requests_ok = False
    _check("requests_none", igd_rig, igd_rig.run_bridge(dm_command("read_requests")))


def test_a_reply_goes_out_in_the_open_inbox_and_is_recorded(igd_rig):
    igd_rig.phone.screen = "inbox"
    _check("send", igd_rig, igd_rig.run_bridge(dm_command("send", username="dave", message="Yes, from ten")))


def test_a_reply_to_a_thread_further_down_scrolls_back_up_and_retries(igd_rig):
    igd_rig.phone.screen = "inbox"
    igd_rig.visible_after = 1
    _check("send_retry", igd_rig, igd_rig.run_bridge(dm_command("send", username="dave", message="Yes")))


def test_a_reply_starting_outside_the_inbox_navigates_to_it(igd_rig):
    _check("send_from_home", igd_rig, igd_rig.run_bridge(dm_command("send", username="dave", message="Yes")))


def test_a_reply_with_instagram_closed_restarts_it(igd_rig):
    igd_rig.instagram_open = False
    _check("send_restart", igd_rig, igd_rig.run_bridge(dm_command("send", username="dave", message="Yes")))


def test_a_reply_to_an_unknown_thread_resolves_our_account(igd_rig):
    igd_rig.phone.screen = "inbox"
    _check("send_unknown_thread", igd_rig, igd_rig.run_bridge(dm_command("send", username="erin", message="Hi")))


def test_a_conversation_that_cannot_be_found_fails(igd_rig):
    igd_rig.phone.screen = "inbox"
    _check("send_not_found", igd_rig, igd_rig.run_bridge(dm_command("send", username="nobody", message="Hi")))


def test_a_message_that_does_not_go_out_fails(igd_rig):
    igd_rig.phone.screen = "inbox"
    igd_rig.send_ok = False
    _check("send_fails", igd_rig, igd_rig.run_bridge(dm_command("send", username="dave", message="Yes")))


def test_a_clone_reply_uses_the_clone(igd_rig):
    igd_rig.instagram_open = False
    _check("send_clone", igd_rig, igd_rig.run_bridge(dm_command("send", username="dave", message="Yes",
                                                                 packageName=CLONE)))
