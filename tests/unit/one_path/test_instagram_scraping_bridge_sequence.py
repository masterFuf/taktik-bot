"""The desktop's Instagram scraping run, frozen: what the bridge asks of the phone and prints.

The snapshot beside this file was recorded from `scraping_bridge` before its config reading moved
into the core and its run into the launcher shared with the CLI. Moving code must not move a
gesture or an output the desktop reads: same device calls, same workflow config, same AI service,
same stdout (the final JSON and the IPC events), same exit code. Set TAKTIK_RECORD_SNAPSHOT=1 to
record it again, on purpose only.
"""
import json
import os
from pathlib import Path

import pytest

from instagram_scraping_rig import (
    hashtag_payload,
    post_url_payload,
    profile_posts_payload,
    target_payload,
    usernames_payload,
)

SNAPSHOT_PATH = Path(__file__).parent / "instagram_scraping_bridge_sequence.json"
RECORD = os.environ.get("TAKTIK_RECORD_SNAPSHOT") == "1"
SNAPSHOT = {} if RECORD else json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _observed(rig, code) -> dict:
    config_path = str(rig.tmp_path / "scraping_config.json")
    observed = {
        "exit": code,
        "calls": rig.calls,
        "stdout": rig.stdout_lines,
        "events": [[kind, payload] for kind, payload in rig.events],
        "configs": rig.configs,
        "ai_builds": rig.ai_builds,
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
    assert observed["configs"] == expected["configs"]
    assert observed["ai_builds"] == expected["ai_builds"]
    assert observed["stdout"] == expected["stdout"]
    assert observed["events"] == expected["events"]
    assert observed["exit"] == expected["exit"]


@pytest.mark.parametrize("name, payload", [
    ("target", target_payload()),
    ("hashtag_ai", hashtag_payload()),
    ("post_url", post_url_payload()),
    ("usernames", usernames_payload()),
    ("profile_posts", profile_posts_payload()),
    ("single_hashtag", hashtag_payload(hashtags=None, hashtag="viral", ai=None)),
    ("single_post_url", post_url_payload(postUrls=None, postUrl="https://www.instagram.com/p/One1/")),
    ("bare", {"deviceId": "emulator-5554"}),
])
def test_a_page_payload_runs_exactly_as_recorded(igs_rig, name, payload):
    _check(name, igs_rig, igs_rig.run_bridge(payload))


def test_a_run_that_reports_a_failure_prints_it(igs_rig):
    igs_rig.run_result = {"success": False, "total_scraped": 0, "completion_reason": "source_unreachable",
                          "error": "followers list not reached"}
    _check("run_failed", igs_rig, igs_rig.run_bridge(target_payload()))


def test_a_run_that_raises_prints_the_error(igs_rig):
    igs_rig.run_raises = RuntimeError("uiautomator died")
    _check("run_raises", igs_rig, igs_rig.run_bridge(target_payload()))


def test_a_device_that_does_not_connect_stops_the_run(igs_rig):
    igs_rig.connect_ok = False
    _check("no_connection", igs_rig, igs_rig.run_bridge(target_payload()))


def test_a_payload_without_device_is_refused(igs_rig):
    _check("no_device", igs_rig, igs_rig.run_bridge(target_payload(deviceId=None)))


def test_no_config_file_is_refused(igs_rig):
    _check("no_argument", igs_rig, igs_rig.run_bridge(None, argv=["scraping_bridge"]))


def test_an_unreadable_config_is_refused(igs_rig):
    _check("unreadable", igs_rig, igs_rig.run_bridge("{not json"))
