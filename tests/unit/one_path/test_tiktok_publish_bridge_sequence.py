"""The desktop's TikTok publication, frozen: what `tiktok_publish_bridge` asks of the phone, what
it prints and its exit code.

The snapshot beside this file was recorded while the reading of the config, the clone patch and
the choice between a video upload and a text post still lived in the bridge, before they moved
into the core launcher (`run_tiktok_publish`). The upload workflow, the text post, the connection
and the clone patch are fakes; the bridge's screenshots are recorded, not written. Same device
calls, same stdout events in the same order, same exit code.

`text_refused` was recorded on both codes (TikTok's refusal on screen after the text post); its old
values stay beside the new ones. The payload carries `botUsername`, as the app writes it.
"""
import json
from pathlib import Path

import pytest

SNAPSHOT_PATH = Path(__file__).parent / "tiktok_publish_bridge_sequence.json"
SNAPSHOT = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

CLONE = "com.example.tiktokclone"


def scenario(name, rig, publish_payload):
    """The config file of one recorded run (None: no argument); the phone is set on `rig`."""
    if name == "video":
        return publish_payload()
    if name == "video_clone_package":
        return publish_payload(packageName=CLONE)
    if name == "video_official_package":
        return publish_payload(packageName="com.zhiliaoapp.musically")
    if name == "video_clone_patch_fails":
        rig.clone_patch_raises = True
        return publish_payload(packageName=CLONE)
    if name == "video_fails":
        rig.upload_outcome = {"success": False, "message": "Publish button not found",
                              "error_type": "publish_button_not_found"}
        return publish_payload()
    if name == "video_raises":
        rig.upload_raises = True
        return publish_payload()
    if name == "text":
        return publish_payload("text")
    if name == "text_to_story_on_clone":
        return publish_payload("text", toStory=True, packageName=CLONE)
    if name == "text_fails":
        rig.text_post_outcome = {"success": False, "step": "mode_text", "typed": "",
                                 "destination": "feed",
                                 "error": "the TEXT mode is not offered on this creation screen"}
        return publish_payload("text")
    if name == "text_refused":
        rig.text_post_refused = True
        return publish_payload("text")
    if name == "text_raises":
        rig.text_post_raises = True
        return publish_payload("text")
    if name == "connect_fails":
        rig.publish_connects = False
        return publish_payload()
    if name == "no_device":
        payload = publish_payload()
        payload.pop("deviceId")
        return payload
    if name == "video_without_file":
        payload = publish_payload()
        payload.pop("localPath")
        return payload
    if name == "text_without_text":
        return publish_payload("text", text="   ")
    if name == "no_config_argument":
        return None
    if name == "unreadable_config":
        return "{not json"
    raise KeyError(name)


SCENARIOS = (
    "video", "video_clone_package", "video_official_package", "video_clone_patch_fails",
    "video_fails", "video_raises", "text", "text_to_story_on_clone", "text_fails", "text_refused",
    "text_raises",
    "connect_fails", "no_device", "video_without_file", "text_without_text", "no_config_argument",
    "unreadable_config",
)


def _events(rig):
    """A traceback names files and lines of whichever code raised: kept as proof it is sent."""
    for kind, event in rig.events:
        if kind == "log" and str(event.get("message", "")).startswith("Traceback"):
            event = {**event, "message": "<traceback>"}
        yield [kind, event]


def observe(rig, name, publish_payload):
    code = rig.run_publish_bridge(scenario(name, rig, publish_payload))
    # JSON round trip: the snapshot holds what went over the wire, not Python types.
    return json.loads(json.dumps({"exit": code, "calls": rig.calls, "events": list(_events(rig))}))


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_bridge_runs_exactly_as_recorded(rig, publish_payload, name):
    assert name in SNAPSHOT, f"no recording for {name}"
    observed = observe(rig, name, publish_payload)
    expected = SNAPSHOT[name]

    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["exit"] == expected["exit"]


def test_every_recording_is_a_scenario():
    assert sorted(SNAPSHOT) == sorted(SCENARIOS)


def test_a_refused_text_post_is_reported_and_filed_under_the_account():
    """`text_refused`: TikTok refuses the text post. The old code reported it published; now the
    run fails on `action_blocked` and the refusal is one health entry of the account the app
    names (`botUsername`), which then rests."""
    record = SNAPSHOT["text_refused"]
    assert record["events_old_code"][-1][1]["success"] is True
    assert record["events"][-1] == ["upload_result", {
        "success": False, "workflow": "text_post",
        "message": "TikTok refuses the publication (Too many requests)", "error_type": "action_blocked"}]
    assert record["calls"][-1] == "health tiktok my_account action_blocked PUBLISH"
    assert record["exit"] == 1 and record["exit_old_code"] == 0
