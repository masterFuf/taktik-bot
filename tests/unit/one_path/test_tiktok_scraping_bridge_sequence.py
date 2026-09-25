"""The desktop's TikTok scraping, frozen: what its two bridges ask of the phone, what they print,
the config they build and what they write.

The app starts a scraping run through `tiktok_scraping_bridge` (one JSON line on stdin); the
`tiktok_bridge` dispatcher also routes `workflowType: scraping` to the same runner. The snapshot
beside this file was recorded from both while the reading of the payload, the session start, the
live events and the scraping session rows still lived in the bridge, before they moved into the
core launcher (`run_tiktok_scraping`) and the stdin bridge onto `run_bridge_main`. Same device
calls, same stdout events in the same order, same workflow config, same rows handed to the
database, same stop handlers, same exit code.

Recordings that changed on purpose keep the old code's values beside the new ones
(`*_old_code`): a target run without an account and a hashtag run without a hashtag are refused
before the phone is touched (the old bridge restarted TikTok, then scraped nothing and called it
a success), and an empty stdin reports the shared entrypoint's words. The app sends none of them:
the page and the scheduler refuse both runs, and the main process always writes the payload.
"""
import dataclasses
import json
import signal
from pathlib import Path
from types import SimpleNamespace

import pytest

SNAPSHOT_PATH = Path(__file__).parent / "tiktok_scraping_bridge_sequence.json"
SNAPSHOT = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

#: Stands for the wall-clock stamp of a `scraping_profile` event.
NOW = "<now>"


def scenario(name, rig, scraping_payload):
    """What one recorded run is given: the phone and the database are set on `rig`; returns the
    stdin (a payload, or raw text) and which bridge receives it."""
    rig.install_scraping_database()
    stdin = "stdin"
    if name.startswith("dispatcher_"):
        stdin, name = "dispatcher", name[len("dispatcher_"):]

    if name in ("page_target", "page_hashtag", "page_post_url", "page_sound", "page_account_posts"):
        return scraping_payload(name[len("page_"):]), stdin
    if name == "scheduler_node":
        return scraping_payload("scheduler_node"), stdin
    if name == "without_saving":
        return scraping_payload(saveToDb=False), stdin
    if name == "session_not_created":
        rig.scraping_session_id = None
        return scraping_payload(), stdin
    if name in ("max_duration_reached", "stopped_by_user"):
        rig.scraping_reason = name
        return scraping_payload(sessionDurationMinutes=20), stdin
    if name == "source_error":
        rig.scraping_error = "Could not open https://vm.tiktok.com/ZNexample/"
        return scraping_payload("post_url"), stdin
    if name == "workflow_raises":
        rig.scraping_raises = True
        return scraping_payload(), stdin
    if name == "start_fails":
        rig.restart_ok = False
        return scraping_payload(), stdin
    if name == "target_without_accounts":
        return scraping_payload(targetUsernames=[]), stdin
    if name == "hashtag_without_name":
        return scraping_payload("hashtag", hashtag=""), stdin
    if name == "no_device":
        payload = scraping_payload()
        payload.pop("deviceId")
        return payload, stdin
    if name == "empty_stdin":
        return "", stdin
    if name == "invalid_json":
        return "{not json\n", stdin
    raise KeyError(name)


SCENARIOS = (
    "page_target", "page_hashtag", "page_post_url", "page_sound", "page_account_posts",
    "scheduler_node", "without_saving", "session_not_created", "max_duration_reached",
    "stopped_by_user", "source_error", "workflow_raises", "start_fails", "target_without_accounts",
    "hashtag_without_name", "no_device", "empty_stdin", "invalid_json",
    "dispatcher_page_target", "dispatcher_page_post_url", "dispatcher_start_fails",
    "dispatcher_target_without_accounts",
)


def _stamped(events):
    """`scrapedAt` is the wall clock: kept as proof it is there, not as a value."""
    for kind, event in events:
        if kind == "scraping_profile" and "scrapedAt" in event:
            assert isinstance(event["scrapedAt"], str) and event["scrapedAt"][:2] == "20", event
            event = {**event, "scrapedAt": NOW}
        yield [kind, event]


def observe(rig, name, scraping_payload):
    payload, bridge = scenario(name, rig, scraping_payload)
    if bridge == "dispatcher":
        code = rig.run_bridge(payload)
    else:
        code = rig.run_scraping_bridge(payload)
    # JSON round trip: the snapshot holds what went over the wire, not Python types.
    return json.loads(json.dumps({
        "exit": code,
        "calls": rig.calls,
        "events": list(_stamped(rig.events)),
        "configs": [dataclasses.asdict(config) for config in rig.built_configs],
        "db_writes": rig.db_writes,
        "signals": sorted(signal.Signals(number).name for number in rig.signal_handlers),
    }))


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_bridge_runs_exactly_as_recorded(rig, scraping_payload, name):
    assert name in SNAPSHOT, f"no recording for {name}"
    observed = observe(rig, name, scraping_payload)
    expected = SNAPSHOT[name]

    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["configs"] == expected["configs"]
    assert observed["db_writes"] == expected["db_writes"]
    assert observed["signals"] == expected["signals"]
    assert observed["exit"] == expected["exit"]


def test_every_recording_is_a_scenario():
    assert sorted(SNAPSHOT) == sorted(SCENARIOS)


def test_a_run_with_nothing_to_scrape_is_refused_before_the_phone_is_touched():
    changed = {name: record for name, record in SNAPSHOT.items() if "calls_old_code" in record}
    assert sorted(changed) == [
        "dispatcher_target_without_accounts", "hashtag_without_name", "target_without_accounts",
    ]
    for name, record in changed.items():
        # The dispatcher force-stops TikTok after any run, refused or not.
        assert record["calls"] in ([], ["force_stop tiktok"]), name
        assert record["calls_old_code"][:2] == ["manager emulator-5554", "restart"], name
        assert record["events"][-1][0] == "error", name
        assert record["exit"] == 1 and record["exit_old_code"] == 0, name
        assert record["db_writes"] == [] and record["configs"] == [], name


def test_an_empty_stdin_reports_the_shared_entrypoint_words():
    record = SNAPSHOT["empty_stdin"]
    assert record["events_old_code"] == [["error", {"error": "No configuration received"}]]
    assert record["events"] == [["error", {"error": "No config received from stdin"}]]
    assert record["calls"] == [] and record["exit"] == 1


def test_a_stop_signal_stops_the_run_and_exits_cleanly(rig, scraping_payload):
    """The stdin bridge's SIGTERM: the registered workflow is asked to stop, the process exits 0."""
    from bridges.common.runtime import bridge_base

    rig.install_scraping_database()
    rig.run_scraping_bridge(scraping_payload())
    stopped = []
    bridge_base.set_workflow(SimpleNamespace(stop=lambda: stopped.append(True)))

    with pytest.raises(SystemExit) as exit_info:
        rig.signal_handlers[signal.SIGTERM](signal.SIGTERM, None)

    assert exit_info.value.code == 0
    assert stopped == [True]
