"""One Followers or Target Profiles config, one run: the desktop bridge and the CLI do the same
thing with it.

The CLI's handler took one target (`searchQuery`) and dropped the list the page sends
(`targets`, `targetAccounts`), gave that target the whole budget, read "1 %" as 100 %, ignored
the comment texts and started nothing: no clean restart, no language detection, no account to act
as, no AI. Target Profiles had no handler at all.
"""
from dataclasses import asdict

AI_KEY = "sk-or-v1-" + "a" * 48

_BRIDGE_PROCESS_ONLY = {"force_stop tiktok"}


def _configs(rig):
    # Every flat key of a TikTok config also lands in `filters` (the evaluator reads only its
    # criteria there); the CLI adds the serial under a second name, `device_id`.
    configs = []
    for config in rig.built_configs:
        data = asdict(config)
        data["filters"] = {key: value for key, value in data["filters"].items() if key != "device_id"}
        configs.append(data)
    return configs


def _run_both(rig, payload, workflow_id="tiktok.automation.followers", env=None):
    rig.run_bridge(payload)
    bridge = {
        "configs": _configs(rig),
        "calls": [call for call in rig.calls if call not in _BRIDGE_PROCESS_ONLY],
        "ai": list(rig.ai_installs),
    }
    rig.calls.clear()
    rig.workflows.clear()
    rig.ai_installs.clear()

    result = rig.run_cli(payload, env=env, workflow_id=workflow_id)
    assert result.exit_code == 0, result.output
    cli = {"configs": _configs(rig), "calls": list(rig.calls), "ai": list(rig.ai_installs)}
    return bridge, cli


def test_the_cli_walks_every_target_with_the_budget_the_bridge_gives_it(rig, followers_payload):
    bridge, cli = _run_both(rig, followers_payload())

    assert [c["search_query"] for c in cli["configs"]] == ["alpha", "beta"]
    assert [c["max_followers"] for c in cli["configs"]] == [2, 1]
    assert cli["configs"] == bridge["configs"]


def test_the_profile_budget_is_a_ceiling_even_below_the_number_of_targets(rig, followers_payload):
    """The bridge gave every target at least one profile: `maxFollowers` 1 on two targets visited
    3 profiles (2 + 1). The budget now caps the run: the first target, one profile."""
    bridge, cli = _run_both(rig, followers_payload(maxFollowers=1))

    assert [(c["search_query"], c["max_followers"]) for c in bridge["configs"]] == [("alpha", 1)]
    assert "return_home" not in bridge["calls"]
    assert cli["configs"] == bridge["configs"]


def test_the_cli_carries_the_session_limits_over_from_one_target_to_the_next(rig, followers_payload):
    bridge, cli = _run_both(rig, followers_payload())

    assert [(c["max_likes_per_session"], c["max_follows_per_session"]) for c in cli["configs"]] == [
        (40, 15), (39, 14)]
    assert cli["configs"] == bridge["configs"]


def test_the_cli_reads_the_probabilities_and_comment_texts_like_the_bridge(rig, followers_payload):
    payload = followers_payload(commentProbability=20, commentTexts=["Nice one"])
    bridge, cli = _run_both(rig, payload)

    first = cli["configs"][0]
    assert first["like_probability"] == 0.01
    assert first["comment_probability"] == 0.2
    assert first["comment_texts"] == ["Nice one"]
    assert cli["configs"] == bridge["configs"]


def test_the_cli_starts_moves_between_targets_and_acts_as_the_account_like_the_bridge(
        rig, followers_payload):
    bridge, cli = _run_both(rig, followers_payload())

    assert cli["calls"] == bridge["calls"]
    assert cli["calls"][:3] == ["manager emulator-5554", "restart", "wait_app_surface"]
    assert "detect_language" in cli["calls"]
    assert cli["calls"].count("return_home") == 1
    assert cli["calls"].count("workflow_run as acting_account") == 2


def test_the_scheduler_shape_runs_every_target_from_the_cli_too(rig, followers_payload):
    """The node sends the first target as `searchQuery` beside the list: the list wins."""
    payload = followers_payload(searchQuery="alpha", targets=["alpha", "beta"], maxVideos=3)
    bridge, cli = _run_both(rig, payload)

    assert [c["search_query"] for c in cli["configs"]] == ["alpha", "beta"]
    assert cli["configs"] == bridge["configs"]


def test_a_run_with_ai_installs_the_same_hooks_from_both_paths(rig, followers_payload):
    payload = followers_payload(ai={"enabled": True, "profileAnalysis": True, "openrouterApiKey": AI_KEY})
    bridge, cli = _run_both(rig, payload)

    assert bridge["ai"], "the bridge installed no AI hooks"
    assert cli["ai"] == bridge["ai"]


def test_the_cli_runs_a_target_profiles_list_like_the_bridge(rig, followers_payload):
    payload = followers_payload(workflowType="target_profiles", profiles=["alpha", "@beta"])
    bridge, cli = _run_both(rig, payload, "tiktok.automation.target_profiles")

    assert [c["usernames"] for c in cli["configs"]] == [["alpha", "beta"]]
    assert [c["max_followers"] for c in cli["configs"]] == [3]
    assert cli["configs"] == bridge["configs"]
    assert cli["calls"] == bridge["calls"]
