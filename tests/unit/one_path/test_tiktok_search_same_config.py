"""One Search or Hashtag config, one run: the desktop bridge and the CLI do the same thing with it.

The CLI's handler took one query and dropped the list (`hashtags`, `searchQueries`), did not share
the video budget between queries, read no comment or repost setting, read "1 %" as 100 % and
started nothing: no clean restart, no language detection, no AI.
"""
from dataclasses import asdict

AI_KEY = "sk-or-v1-" + "a" * 48

_BRIDGE_PROCESS_ONLY = {"force_stop tiktok"}


def _payload(page_payload, **overrides):
    payload = page_payload(workflowType="hashtag", searchQuery="run", hashtags=["run", "#trail", "run"],
                           commentTexts=["Nice one"])
    payload.update(overrides)
    return payload


def _run_both(rig, payload, workflow_id, env=None):
    rig.run_bridge(payload)
    bridge = {
        "configs": [asdict(config) for config in rig.built_configs],
        "calls": [call for call in rig.calls if call not in _BRIDGE_PROCESS_ONLY],
        "ai": list(rig.ai_installs),
    }
    rig.calls.clear()
    rig.workflows.clear()
    rig.ai_installs.clear()

    result = rig.run_cli(payload, env=env, workflow_id=workflow_id)
    assert result.exit_code == 0, result.output
    cli = {"configs": [asdict(config) for config in rig.built_configs], "calls": list(rig.calls),
           "ai": list(rig.ai_installs)}
    return bridge, cli


def test_the_cli_runs_every_hashtag_with_the_budget_the_bridge_gives_it(rig, page_payload):
    bridge, cli = _run_both(rig, _payload(page_payload), "tiktok.automation.hashtag")

    assert [c["search_query"] for c in cli["configs"]] == ["run", "trail"]
    assert [c["max_videos"] for c in cli["configs"]] == [3, 2]
    assert cli["configs"] == bridge["configs"]


def test_the_cli_reads_the_comment_and_probability_settings_like_the_bridge(rig, page_payload):
    bridge, cli = _run_both(rig, _payload(page_payload), "tiktok.automation.hashtag")

    first = cli["configs"][0]
    assert first["like_probability"] == 0.01
    assert first["comment_probability"] == 0.2
    assert first["comment_texts"] == ["Nice one"]
    assert cli["configs"][0] == bridge["configs"][0]


def test_the_cli_starts_and_moves_between_queries_like_the_bridge(rig, page_payload):
    bridge, cli = _run_both(rig, _payload(page_payload), "tiktok.automation.hashtag")

    assert cli["calls"] == bridge["calls"]
    assert cli["calls"][:3] == ["manager emulator-5554", "restart", "wait_app_surface"]
    assert "detect_language" in cli["calls"]
    assert "return_home" in cli["calls"]


def test_a_search_with_ai_installs_the_same_hooks_from_both_paths(rig, page_payload):
    payload = _payload(page_payload, workflowType="search", searchQuery="street food",
                       searchQueries=["street food"], language="fr",
                       ai={"enabled": True, "profileAnalysis": True, "openrouterApiKey": AI_KEY})
    payload.pop("hashtags")
    bridge, cli = _run_both(rig, payload, "tiktok.automation.search")

    assert bridge["ai"], "the bridge installed no AI hooks"
    assert cli["ai"] == bridge["ai"]
    assert cli["configs"] == bridge["configs"]
