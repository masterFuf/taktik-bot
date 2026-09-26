"""One Instagram automation config, one run: the desktop bridge and the CLI must do the same thing.

The scheduler reaches the bot through the very bridge the pages use, so these two paths are the
three. The CLI ran the Agent handler, which kept an older subset of the payload (the warmup caps,
the pacing profile, the feed settings, the split between sources were lost) and restarted nothing:
the workflow config says Instagram was restarted by the host, and in the terminal no host did it.
"""

from instagram_rig import AI_KEY, INSTAGRAM, feed_payload, target_payload

# Steps that belong to the desktop process, not to the run: the stats wiring, the database setup,
# the bridge's own connection and its uiautomator2 check, the IP baseline, the final app stop.
_HOST_ONLY = ("stats_callback", "configure_db", "connect ", "network_baseline ", "atx_health ")


def _run_steps(calls: list[str]) -> list[str]:
    steps = [call for call in calls if not call.startswith(_HOST_ONLY)]
    # The bridge stops Instagram when its process ends.
    if steps and steps[-1].startswith("stop ") and "run_workflow" in steps:
        steps = steps[:-1]
    return steps


def _run_both(rig, payload, env=None):
    code = rig.run_bridge(payload)
    assert code == 0, rig.events
    bridge = {"config": rig.built_config, "steps": _run_steps(rig.calls), "ai": list(rig.ai_installs)}
    rig.reset()

    result = rig.run_cli(payload, env=env)
    assert result.exit_code == 0, result.output
    cli = {"config": rig.built_config, "steps": _run_steps(rig.calls), "ai": list(rig.ai_installs)}
    return bridge, cli


def test_the_cli_builds_the_config_the_bridge_builds(ig_rig):
    bridge, cli = _run_both(ig_rig, feed_payload())

    assert cli["config"] == bridge["config"]
    assert cli["config"]["session_settings"]["warmup_policy"]["max_actions_per_session"] == 20
    assert cli["config"]["behaviorPolicy"] == {"profile": "prudent"}
    assert cli["config"]["actions"][0]["browse_carousels"] is False


def test_a_target_run_keeps_its_sources_filters_and_warmup_in_the_cli(ig_rig):
    bridge, cli = _run_both(ig_rig, target_payload())

    assert cli["config"] == bridge["config"]
    action = cli["config"]["actions"][0]
    assert action["target_usernames"] == ["alpha", "beta"]
    assert action["distribution"] == "sequential"
    assert cli["config"]["session_settings"]["warmup_policy"]["min_action_gap_seconds"] == 8


def test_the_cli_restarts_instagram_the_way_the_bridge_does(ig_rig):
    bridge, cli = _run_both(ig_rig, feed_payload())

    assert cli["steps"] == bridge["steps"]
    assert cli["steps"][:3] == [f"is_installed {INSTAGRAM}", f"stop {INSTAGRAM}",
                                f"launch {INSTAGRAM} com.instagram.mainactivity.InstagramMainActivity stop_first=False"]
    assert "version_overrides 410.0.0.53.71" in cli["steps"]


def test_a_clone_is_restarted_and_patched_the_same_way(ig_rig):
    bridge, cli = _run_both(ig_rig, feed_payload(packageName="com.taktik.ig1"))

    assert cli["steps"] == bridge["steps"]
    assert "clone_patch com.taktik.ig1" in cli["steps"]


def test_an_ai_run_installs_the_same_hooks_from_both_paths(ig_rig):
    payload = target_payload(ai={"enabled": True, "profileAnalysis": True, "openrouterApiKey": AI_KEY})
    bridge, cli = _run_both(ig_rig, payload)

    assert bridge["ai"], "the bridge installed no AI hooks"
    assert cli["ai"] == bridge["ai"]


def test_the_cli_takes_the_openrouter_key_from_the_environment(ig_rig):
    payload = target_payload(ai={"enabled": True, "profileAnalysis": True})

    result = ig_rig.run_cli(payload, env={"OPENROUTER_API_KEY": AI_KEY})

    assert result.exit_code == 0, result.output
    assert [service["key"] for service in ig_rig.ai_services] == [AI_KEY]
    assert len(ig_rig.ai_installs) == 1


def test_without_a_key_a_scripted_ai_run_is_refused_before_the_phone(ig_rig):
    """`--json` is a scripted run: nobody to ask for the key, so the run stops, exit 2, and says
    how to give it. It used to go on without AI, which is not the run that was asked for."""
    result = ig_rig.run_cli(target_payload(ai={"enabled": True, "profileAnalysis": True}),
                            env={"OPENROUTER_API_KEY": ""})

    assert result.exit_code == 2, result.output
    assert "OPENROUTER_API_KEY" in result.output
    assert ig_rig.workflows == []
    assert ig_rig.ai_installs == [] and ig_rig.ai_services == []


def test_a_manual_run_needs_no_key(ig_rig):
    result = ig_rig.run_cli(target_payload(), env={"OPENROUTER_API_KEY": ""})

    assert result.exit_code == 0, result.output
    assert ig_rig.workflows
    assert ig_rig.ai_installs == [] and ig_rig.ai_services == []


def test_the_cli_does_not_run_when_instagram_is_missing(ig_rig):
    ig_rig.installed = False

    result = ig_rig.run_cli(feed_payload())

    assert result.exit_code == 1, result.output
    assert "run_workflow" not in ig_rig.calls
