"""One For You config, one run: the desktop bridge and the CLI must do the same thing with it.

The scheduler reaches the bot through the very bridge the page uses, so these two paths are the
three. The CLI used to run the Agent handler, which read an older subset of the payload (no
comments, reposts or feed training, "1 %" read as 100 %) and started nothing: no clean restart,
no language detection, no account.
"""
from dataclasses import asdict

from loguru import logger

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
    assert [install["ai_config"]["openrouterApiKey"] for install in rig.ai_installs] == [AI_KEY]


def test_without_a_key_the_cli_runs_without_ai_and_says_why(rig, page_payload):
    warnings = []
    sink = logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        result = rig.run_cli(page_payload(ai={"enabled": True, "profileAnalysis": True}))
    finally:
        logger.remove(sink)

    assert result.exit_code == 0, result.output
    assert rig.ai_installs == []
    assert rig.workflows, "the run must go on without AI"
    assert any("OPENROUTER_API_KEY" in line for line in warnings)
