"""One Post URL config, one run: the desktop bridge and the CLI do the same thing with it.

The CLI had no id for this workflow (`tiktok.automation.post_url` was unknown): the link, the
commenter and visit budgets, the interaction settings, the start and the AI hooks were the
bridge's alone.
"""
from dataclasses import asdict

AI_KEY = "sk-or-v1-" + "a" * 48
WORKFLOW_ID = "tiktok.automation.post_url"

_BRIDGE_PROCESS_ONLY = {"force_stop tiktok"}


def _configs(rig):
    # Every flat key also lands in `filters`; the CLI adds the serial there as `device_id`.
    configs = []
    for config in rig.built_configs:
        data = asdict(config)
        data["filters"] = {key: value for key, value in data["filters"].items() if key != "device_id"}
        configs.append(data)
    return configs


def _observed(rig):
    return {
        "configs": _configs(rig),
        "device_ids": [workflow.device_id for workflow in rig.workflows],
        "calls": [call for call in rig.calls if call not in _BRIDGE_PROCESS_ONLY],
        "ai": list(rig.ai_installs),
    }


def _run_both(rig, payload, env=None):
    rig.run_bridge(payload)
    bridge = _observed(rig)
    rig.forget_run()

    result = rig.run_cli(payload, env=env, workflow_id=WORKFLOW_ID)
    assert result.exit_code == 0, result.output
    return bridge, _observed(rig)


def test_the_cli_runs_the_post_url_the_bridge_runs(rig, post_url_payload):
    bridge, cli = _run_both(rig, post_url_payload())

    first = cli["configs"][0]
    assert first["post_url"] == "https://www.tiktok.com/@creator/video/1"
    assert (first["max_commenters"], first["max_followers"]) == (12, 5)
    assert first["like_probability"] == 0.01
    assert cli["configs"] == bridge["configs"]
    assert cli["device_ids"] == bridge["device_ids"] == ["emulator-5554"]


def test_the_cli_starts_and_acts_as_the_account_like_the_bridge(rig, post_url_payload):
    bridge, cli = _run_both(rig, post_url_payload())

    assert cli["calls"] == bridge["calls"]
    assert cli["calls"][:3] == ["manager emulator-5554", "restart", "wait_app_surface"]
    assert "detect_language" in cli["calls"]
    assert "workflow_run as acting_account" in cli["calls"]


def test_the_cli_reads_the_budget_the_page_sends_as_max_videos(rig, post_url_payload):
    payload = post_url_payload(maxVideos=7, maxCommenters=20)
    payload.pop("maxProfiles")
    bridge, cli = _run_both(rig, payload)

    assert [c["max_followers"] for c in cli["configs"]] == [7]
    assert cli["configs"] == bridge["configs"]


def test_a_run_with_ai_installs_the_same_hooks_from_both_paths(rig, post_url_payload):
    payload = post_url_payload(ai={"enabled": True, "profileAnalysis": True, "openrouterApiKey": AI_KEY})
    bridge, cli = _run_both(rig, payload)

    assert bridge["ai"], "the bridge installed no AI hooks"
    assert cli["ai"] == bridge["ai"]


def test_without_a_link_neither_path_touches_the_phone(rig, post_url_payload):
    payload = post_url_payload()
    payload.pop("postUrl")

    assert rig.run_bridge(payload) == 1
    assert rig.calls == ["force_stop tiktok"]
    rig.forget_run()

    result = rig.run_cli(payload, workflow_id=WORKFLOW_ID)
    assert result.exit_code == 1
    assert "postUrl" in result.output
    assert rig.calls == []
