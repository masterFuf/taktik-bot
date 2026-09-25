"""One TikTok publish config, one run: the desktop bridge and the CLI publish the same thing the
same way.

The CLI's handler (`tiktok.standalone.upload_post`) had its own reading: video only, so a text
post (`postType: text`) was refused for want of a file; and no clone patch, so a run on a cloned
TikTok (`packageName`) looked for the official app's selectors. What stays with each host: the
bridge opens its own connection and saves before/after screenshots under `debug_ui`, the CLI
brings its connected device and saves nothing.
"""
BRIDGE_ONLY = ("connection ", "capture ")
UPLOAD_ID = "tiktok.standalone.upload_post"


def _phone_calls(calls):
    """What the run asks of the phone and of the selector catalogue, without the host's own steps;
    how the upload workflow was built says which host built it."""
    kept = []
    for call in calls:
        if call == "connect" or call.startswith(BRIDGE_ONLY):
            continue
        kept.append(call.split(" notifier=")[0] if call.startswith("upload_workflow_built") else call)
    return kept


def _run_both(rig, payload, set_phone=lambda: None):
    set_phone()
    bridge_exit = rig.run_publish_bridge(payload)
    bridge = {"exit": bridge_exit, "calls": _phone_calls(rig.calls)}
    rig.forget_run()

    set_phone()
    cli_payload = {key: value for key, value in payload.items() if key != "deviceId"}
    result = rig.run_cli(cli_payload, workflow_id=UPLOAD_ID)
    cli = {"exit": result.exit_code, "calls": _phone_calls(rig.calls),
           "result": rig.cli_results[-1] if rig.cli_results else None, "output": result.output}
    return bridge, cli


def test_a_cli_video_upload_publishes_like_the_bridge(rig, publish_payload):
    bridge, cli = _run_both(rig, publish_payload())

    assert cli["exit"] == bridge["exit"] == 0, cli["output"]
    assert cli["calls"] == bridge["calls"]
    assert any(call.startswith("upload C:/media/clip.mp4") for call in cli["calls"])


def test_a_cli_text_post_publishes_like_the_bridge(rig, publish_payload):
    bridge, cli = _run_both(rig, publish_payload("text", toStory=True))

    assert cli["exit"] == bridge["exit"] == 0, cli["output"]
    assert cli["calls"] == bridge["calls"] == [
        "text_post emulator-5554 'Five kilometres before breakfast' to_story=True"
    ]
    assert cli["result"]["success"] is True


def test_a_cli_publish_on_a_cloned_tiktok_patches_its_selectors_like_the_bridge(rig, publish_payload):
    bridge, cli = _run_both(rig, publish_payload(packageName="com.example.tiktokclone"))

    assert cli["exit"] == 0, cli["output"]
    assert cli["calls"][:2] == ["set_active_package com.example.tiktokclone",
                                "patch_selectors tiktok com.example.tiktokclone"]
    assert cli["calls"] == bridge["calls"]


def test_a_failed_text_post_fails_on_both_paths(rig, publish_payload):
    def set_phone():
        rig.text_post_outcome = {"success": False, "step": "mode_text", "typed": "", "destination": "feed",
                                 "error": "the TEXT mode is not offered on this creation screen"}

    bridge, cli = _run_both(rig, publish_payload("text"), set_phone=set_phone)

    assert bridge["exit"] == cli["exit"] == 1
    assert cli["calls"] == bridge["calls"]


def test_a_video_without_a_file_is_refused_before_the_phone_on_both_paths(rig, publish_payload):
    payload = publish_payload()
    payload.pop("localPath")
    bridge, cli = _run_both(rig, payload)

    assert bridge["exit"] == cli["exit"] == 1
    assert bridge["calls"] == cli["calls"] == []
