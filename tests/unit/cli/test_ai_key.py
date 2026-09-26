"""The CLI asks for the OpenRouter key at launch when the chosen run uses AI, and only then.

Before, a run that asked for AI without a key went on without AI and said so in the log: the
operator got a different run from the one asked for. Now a manual run needs no key; a run that
uses AI finds its key (config, environment, typed, saved) or asks for it at a terminal, with the
option to save it in the bot's settings file (`~/.taktik/api_config.json`, where the API url
already lives); a scripted run without a key stops before the phone with exit code 2.
"""
import json

import pytest
from click.testing import CliRunner

from taktik.cli.common import ai_key
from taktik.cli.common.ai_key import (
    MISSING_KEY_EXIT,
    MissingAIKeyError,
    ensure_ai_key,
    is_interactive,
    resolve_openrouter_key,
    run_uses_ai,
)
from taktik.core.app.config.runtime import user_config


@pytest.fixture(autouse=True)
def _no_key_in_env(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("CI", raising=False)


def _refuse(*_args, **_kwargs):
    raise AssertionError("nobody must be asked")


# --- which runs use AI ----------------------------------------------------------------------

@pytest.mark.parametrize("workflow_id,payload,expected", [
    ("instagram.automation.feed", {}, False),
    ("instagram.automation.feed", {"ai": {"enabled": False, "profileAnalysis": True}}, False),
    ("instagram.automation.feed", {"ai": {"enabled": True}}, True),
    ("instagram.scraping.target", {"ai": {"enabled": True}}, True),
    ("instagram.engagement.coldDm", {"messageMode": "manual"}, False),
    ("instagram.engagement.coldDm", {"messageMode": "ai"}, True),
    ("tiktok.standalone.tiktok_dm_outreach", {"message_mode": "ai"}, True),
    ("tiktok.automation.new_followers", {"ai": {"enabled": True, "newFollowers": {"enabled": True}}}, True),
    ("instagram.engagement.taktik_agent", {}, True),
    ("instagram.automation.feed", {"ai": {"decision": {"mode": "decide"}}}, False),
])
def test_a_run_uses_ai_when_it_asks_for_it(workflow_id, payload, expected):
    assert run_uses_ai(workflow_id, payload) is expected


def test_every_registered_workflow_runs_manually_without_a_key():
    """No workflow of the registry needs a key for a manual run, and none asks for one, even in a
    scripted run with no key anywhere. The Agent is the one run that is AI by nature."""
    from taktik.cli.common.registry_builder import build_registry

    build = build_registry(device=None, device_id="")
    assert build.workflow_ids
    for workflow_id in build.workflow_ids:
        if workflow_id in ai_key.AI_ONLY_WORKFLOWS:
            with pytest.raises(MissingAIKeyError):
                ensure_ai_key(workflow_id, {}, interactive=False)
            continue
        for manual in ({}, {"ai": {"enabled": False}}, {"messageMode": "manual"}):
            assert ensure_ai_key(workflow_id, manual, interactive=False, prompt=_refuse, confirm=_refuse) is None


# --- where the key comes from ---------------------------------------------------------------

def test_the_run_s_own_key_comes_first(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    assert ensure_ai_key("x", {"ai": {"enabled": True, "openrouterApiKey": "from-config"}},
                         interactive=False) == "from-config"
    assert ensure_ai_key("x", {"messageMode": "ai", "openrouterApiKey": "flat"}, interactive=False) == "flat"


def test_the_environment_serves_when_the_run_brings_none(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", " from-env ")
    assert ensure_ai_key("x", {"ai": {"enabled": True}}, interactive=False, prompt=_refuse) == "from-env"


def test_a_saved_key_serves_without_asking():
    user_config.write_user_setting(ai_key.SAVED_KEY_SETTING, "saved-key")
    assert ensure_ai_key("x", {"ai": {"enabled": True}}, interactive=False, prompt=_refuse) == "saved-key"
    assert resolve_openrouter_key() == "saved-key"


# --- no key ---------------------------------------------------------------------------------

def test_a_scripted_run_without_a_key_is_refused_with_how_to_give_it():
    with pytest.raises(MissingAIKeyError) as refused:
        ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True}}, interactive=False, prompt=_refuse)
    message = str(refused.value)
    assert "OPENROUTER_API_KEY" in message
    assert "instagram.automation.feed" in message
    assert user_config.user_config_path() in message


def test_at_a_terminal_the_key_is_asked_hidden_and_saved_on_request():
    user_config.write_user_setting("api_url", "https://api.example.test")
    asked = []

    def prompt(text, **kwargs):
        asked.append(kwargs)
        return " typed-key "

    key = ensure_ai_key("x", {"ai": {"enabled": True}}, interactive=True, prompt=prompt,
                        confirm=lambda *a, **k: True, echo=lambda _m: None)

    assert key == "typed-key"
    assert asked[0]["hide_input"] is True
    saved = json.loads(open(user_config.user_config_path(), encoding="utf-8").read())
    assert saved == {"api_url": "https://api.example.test", "openrouter_api_key": "typed-key"}


def test_a_key_typed_but_not_saved_serves_this_process_only():
    key = ensure_ai_key("x", {"ai": {"enabled": True}}, interactive=True, prompt=lambda *a, **k: "once",
                        confirm=lambda *a, **k: False, echo=lambda _m: None)

    assert key == "once"
    assert resolve_openrouter_key() == "once"
    assert user_config.read_user_setting(ai_key.SAVED_KEY_SETTING) is None


def test_an_empty_answer_is_a_refusal():
    with pytest.raises(MissingAIKeyError):
        ensure_ai_key("x", {"ai": {"enabled": True}}, interactive=True, prompt=lambda *a, **k: "",
                      confirm=_refuse, echo=lambda _m: None)


def test_a_scripted_run_or_ci_is_never_interactive(monkeypatch):
    assert is_interactive(scripted=True) is False
    monkeypatch.setenv("CI", "true")
    assert is_interactive() is False


def test_the_api_url_still_lives_in_the_same_file():
    from taktik.core.app.config.runtime.api_endpoints import APIEndpointManager

    manager = APIEndpointManager()
    assert manager.save_api_url("https://api.example.test/") is True
    assert manager._load_from_config() == "https://api.example.test"
    user_config.write_user_setting(ai_key.SAVED_KEY_SETTING, "k")
    assert manager._load_from_config() == "https://api.example.test"


# --- the commands ---------------------------------------------------------------------------

def _connect_spy(monkeypatch):
    from taktik.cli.commands import workflow_cmds

    connected = []

    def connect(device_id):
        connected.append(device_id)
        return None, ""

    monkeypatch.setattr(workflow_cmds, "_connect", connect)
    return workflow_cmds, connected


def test_workflows_run_refuses_a_scripted_ai_run_without_a_key_before_the_phone(monkeypatch):
    workflow_cmds, connected = _connect_spy(monkeypatch)

    result = CliRunner().invoke(workflow_cmds.workflows, [
        "run", "instagram.automation.feed", "--json", json.dumps({"ai": {"enabled": True}})])

    assert result.exit_code == MISSING_KEY_EXIT == 2
    assert "OPENROUTER_API_KEY" in result.output
    assert connected == []


def test_workflows_run_lets_a_manual_run_through_without_a_key(monkeypatch):
    workflow_cmds, connected = _connect_spy(monkeypatch)

    result = CliRunner().invoke(workflow_cmds.workflows, [
        "run", "instagram.automation.feed", "--json", json.dumps({"limits": {"maxProfiles": 1}})])

    assert connected == [None]
    assert result.exit_code == 1  # no device in the test: the run stops at the connection


def test_workflows_run_asks_at_a_terminal_and_saves(monkeypatch):
    workflow_cmds, connected = _connect_spy(monkeypatch)
    monkeypatch.setattr(workflow_cmds, "is_interactive", lambda scripted=False: not scripted)

    result = CliRunner().invoke(workflow_cmds.workflows, [
        "run", "tiktok.automation.for_you", "--param", "ai={\"enabled\": true}"], input="term-key\ny\n")

    assert "OpenRouter API key" in result.output
    assert "term-key" not in result.output
    assert connected == [None]
    assert user_config.read_user_setting(ai_key.SAVED_KEY_SETTING) == "term-key"


def test_a_dry_run_says_whether_the_key_is_there_without_asking(monkeypatch):
    from taktik.cli.commands import workflow_cmds

    result = CliRunner().invoke(workflow_cmds.workflows, [
        "run", "instagram.automation.feed", "--dry-run", "--json", json.dumps({"ai": {"enabled": True}})])

    assert result.exit_code == 0
    assert "OpenRouter key missing" in result.output


def test_the_agent_handler_takes_the_cli_key_when_the_payload_has_none(monkeypatch):
    """`workflows run instagram.engagement.taktik_agent`: a typed or saved key reaches the Agent,
    which otherwise only looks at its config and the environment."""
    from taktik.core.agent.kernel.contracts import WorkflowInvocation
    from taktik.core.social_media.instagram.workflows.agent import agent_handler

    seen = []
    monkeypatch.setattr(agent_handler, "run_instagram_agent",
                        lambda config, **_kwargs: seen.append(dict(config)) or {"success": True})
    handler = agent_handler.build_instagram_agent_handler(
        instagram_agent_runtime=lambda _package: agent_handler.AgentRuntime(device_manager=None, restart=lambda: True),
        instagram_ai_key=lambda: "cli-key",
    )
    invocation = WorkflowInvocation(platform="instagram", workflow_id=agent_handler.INSTAGRAM_AGENT_WORKFLOW_ID,
                                    params={})

    handler(invocation, {})
    handler(invocation, {"openrouter_api_key": "desktop-key"})

    assert [config["openrouter_api_key"] for config in seen] == ["cli-key", "desktop-key"]
