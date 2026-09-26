"""One Taktik Agent session, one start: the desktop bridge and the CLI prepare the phone the same way.

`taktik agent run` launched Instagram hot on the raw device: no clean restart, the official package
whatever `packageName` said, no clone-aware proxy and the baseline selectors whatever version was
installed. The bridge's start sequence is now the core launcher both call, and the handler
`instagram.engagement.taktik_agent` runs it too.
"""
import pytest

from instagram_agent_rig import CLONE, INSTAGRAM, agent_config

_HOST_ONLY = ("configure_db", "connect", "stop_listener")


def _steps(calls):
    return [call for call in calls if call not in _HOST_ONLY]


@pytest.fixture(autouse=True)
def _guard(no_phone):
    return no_phone


def _params(config):
    return [f"{key}={value}" for key, value in config.items() if key != "deviceId"]


def test_the_cli_restarts_instagram_like_the_bridge(iga_rig):
    config = agent_config()
    assert iga_rig.run_agent_bridge(config) == 0
    bridge = _steps(iga_rig.calls)
    iga_rig.reset()

    result = iga_rig.run_agent_cli(_params(config))

    assert result.exit_code == 0, result.output
    assert _steps(iga_rig.calls) == bridge
    assert f"stop {INSTAGRAM}" in bridge


def test_the_cli_starts_a_clone_on_its_package(iga_rig):
    result = iga_rig.run_agent_cli(_params(agent_config(packageName=CLONE)))

    assert result.exit_code == 0, result.output
    assert iga_rig.calls.index(f"stop {CLONE}") < iga_rig.calls.index(f"launch {CLONE}") \
        < iga_rig.calls.index("agent_workflow")
    assert f"active_package {CLONE}" in iga_rig.calls


def test_the_cli_hands_the_workflow_the_prepared_device_and_the_config(iga_rig):
    result = iga_rig.run_agent_cli(_params(agent_config()))

    assert result.exit_code == 0, result.output
    assert "version_overrides 410.0.0.53.71" in iga_rig.calls
    workflow = iga_rig.workflows[0]
    assert workflow["device_is_phone"] is True
    assert workflow["config"]["max_likes"] == 5 and workflow["config"]["language"] == "fr"


def test_instagram_that_does_not_start_fails_the_cli_run(iga_rig, monkeypatch):
    monkeypatch.setattr(type(iga_rig.device_manager), "launch_app",
                        lambda self, package, activity=None, stop_first=False: False)
    result = iga_rig.run_agent_cli(_params(agent_config()))

    assert result.exit_code == 1
    assert "Failed to launch Instagram" in result.output
    assert iga_rig.workflows == []


def test_the_agent_is_reachable_by_its_manifest_id(iga_rig):
    result = iga_rig.run_cli(agent_config(), workflow_id="instagram.engagement.taktik_agent")

    assert result.exit_code == 0, result.output
    assert f"stop {INSTAGRAM}" in iga_rig.calls and "agent_run" in iga_rig.calls
