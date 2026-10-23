"""One For You config, one run: the desktop bridge and the CLI must do the same thing with it.

The scheduler reaches the bot through the very bridge the page uses, so these two paths are the
three. The CLI used to run the Agent handler, which read an older subset of the payload (no
comments, reposts or feed training, "1 %" read as 100 %) and started nothing: no clean restart,
no language detection, no account.
"""
from dataclasses import asdict


AI_KEY = "sk-or-v1-" + "a" * 48

# The bridge process force-stops the app when it exits; that belongs to the process, not the run.
_BRIDGE_PROCESS_ONLY = {"force_stop tiktok"}


def _run_both(rig, payload, env=None):
    rig.run_bridge(payload)
    bridge = {
        "config": asdict(rig.built_config),
        "calls": [call for call in rig.calls if call not in _BRIDGE_PROCESS_ONLY],
        "ai": list(rig.ai_installs),
    }
    rig.calls.clear()
    rig.workflows.clear()
    rig.ai_installs.clear()

    result = rig.run_cli(payload, env=env)
    assert result.exit_code == 0, result.output
    cli = {"config": asdict(rig.built_config), "calls": list(rig.calls), "ai": list(rig.ai_installs)}
    return bridge, cli


def test_the_cli_builds_the_config_the_bridge_builds(rig, page_payload):
    bridge, cli = _run_both(rig, page_payload())

    assert cli["config"] == bridge["config"]
    assert cli["config"]["like_probability"] == 0.01
    assert cli["config"]["comment_probability"] == 0.2
    assert cli["config"]["training_keywords"] == ["running", "trail"]


def test_the_cli_starts_the_app_the_way_the_bridge_does(rig, page_payload):
    bridge, cli = _run_both(rig, page_payload())

    assert cli["calls"] == bridge["calls"]
    assert cli["calls"][:3] == ["manager emulator-5554", "restart", "wait_app_surface"]
    assert "detect_language" in cli["calls"]


def test_an_ai_run_installs_the_same_hooks_from_both_paths(rig, page_payload):
    payload = page_payload(ai={"enabled": True, "profileAnalysis": True, "openrouterApiKey": AI_KEY},
                           language="fr")
    bridge, cli = _run_both(rig, payload)

    assert bridge["ai"], "the bridge installed no AI hooks"
    assert cli["ai"] == bridge["ai"]


def test_the_cli_takes_the_openrouter_key_from_the_environment(rig, page_payload):
    payload = page_payload(ai={"enabled": True, "profileAnalysis": True}, language="fr")

    result = rig.run_cli(payload, env={"OPENROUTER_API_KEY": AI_KEY})

    assert result.exit_code == 0, result.output
    assert [(install["ai_config"]["provider"], install["ai_config"]["apiKey"])
            for install in rig.ai_installs] == [("openrouter", AI_KEY)]


def test_without_a_key_a_scripted_ai_run_is_refused_before_the_phone(rig, page_payload):
    result = rig.run_cli(page_payload(ai={"enabled": True, "profileAnalysis": True}))

    assert result.exit_code == 2, result.output
    assert "OPENROUTER_API_KEY" in result.output
    assert rig.ai_installs == [] and rig.ai_services == []
    assert rig.workflows == [] and rig.calls == []


def _error_codes(events) -> list:
    return [fields.get("error_code") for kind, fields in events if kind == "error"]


def test_a_phone_without_network_does_not_start_its_run_from_either_path(rig, page_payload):
    """No route at all: the desktop refused the run at its bridge's door and the CLI ran it. Both now
    refuse it at the TikTok session start, with the same motive, before TikTok restarts."""
    rig.network.cut()

    assert rig.run_bridge(page_payload()) == 1
    assert _error_codes(rig.events)[-1] == "NETWORK_UNREACHABLE"
    assert "restart" not in rig.calls and rig.workflows == []
    rig.calls.clear()
    rig.events.clear()

    result = rig.run_cli(page_payload())

    assert result.exit_code == 1, result.output
    assert "NETWORK_UNREACHABLE" in result.output
    assert "restart" not in rig.calls and rig.workflows == []
