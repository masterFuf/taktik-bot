"""The CLI asks for an AI key at launch when the chosen run uses AI, and only then.

Before, a run that asked for AI without a key went on without AI and said so in the log: the
operator got a different run from the one asked for. Now a manual run needs no key; a run that
uses AI finds its key (config, environment, typed, saved) or asks for it at a terminal, with the
option to save it in the bot's settings file (`~/.taktik/api_config.json`, where the API url
already lives); a scripted run without a key stops before the phone with exit code 2.

The key comes with its provider (`AICredential`): OpenRouter, or Anthropic (an `ANTHROPIC_API_KEY`,
an `sk-ant-` key typed at the terminal, a run's `provider: "anthropic"`). OpenRouter comes first when
both are known: the measured models are there.
"""
import json

import pytest
from click.testing import CliRunner

from taktik.cli.hosts import ai_key
from taktik.cli.hosts.ai_key import (
    MISSING_KEY_EXIT,
    MissingAIKeyError,
    ensure_ai_key,
    is_interactive,
    resolve_cli_credential,
)
from taktik.core.ai.credential import AICredential
from taktik.core.contract.ai_request import asks_for_ai
from taktik.core.shared.config import user_config

ANTHROPIC_KEY = "sk-ant-api03-" + "a" * 40


@pytest.fixture(autouse=True)
def _no_key_in_env(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CI", raising=False)


def _refuse(*_args, **_kwargs):
    raise AssertionError("nobody must be asked")


def _openrouter(key):
    return AICredential(provider="openrouter", api_key=key)


# --- which runs use AI ----------------------------------------------------------------------

def test_the_cli_asks_for_a_key_where_the_engine_declares_the_ai_and_nowhere_else():
    """The rule is the engine's declaration (`WorkflowContract.ai_request`, held by
    `tests/unit/contract/test_workflow_contract_ai_request.py`): the CLI keeps none of its own, so a
    workflow that declares no request gets no key asked for, whatever its payload carries."""
    assert ensure_ai_key("tiktok.standalone.tiktok_unfollow", {"ai": {"enabled": True}}, interactive=False,
                         prompt=_refuse) is None
    with pytest.raises(MissingAIKeyError):
        ensure_ai_key("instagram.engagement.coldDm", {"messageMode": "ai"}, interactive=False, prompt=_refuse)
    with pytest.raises(MissingAIKeyError):
        ensure_ai_key("tiktok.standalone.tiktok_dm_outreach", {"message_mode": "ai"}, interactive=False, prompt=_refuse)
    assert not hasattr(ai_key, "run_uses_ai"), "the CLI reads the engine's rule, it does not write a second one"
    assert asks_for_ai is ai_key.asks_for_ai


def test_every_registered_workflow_runs_manually_without_a_key():
    """No workflow of the registry needs a key for a manual run, and none asks for one, even in a
    scripted run with no key anywhere. The Agent is the one run that is AI by nature."""
    from taktik.cli.hosts.registry import build_registry
    from taktik.core.contract.registry import WORKFLOW_CONTRACTS

    by_nature = {workflow_id for contract in WORKFLOW_CONTRACTS if contract.ai_request and contract.ai_request.always
                 for workflow_id in contract.serves}
    build = build_registry(device=None, device_id="")
    assert build.workflow_ids and by_nature
    for workflow_id in build.workflow_ids:
        if workflow_id in by_nature:
            with pytest.raises(MissingAIKeyError):
                ensure_ai_key(workflow_id, {}, interactive=False)
            continue
        for manual in ({}, {"ai": {"enabled": False}}, {"messageMode": "manual"}):
            assert ensure_ai_key(workflow_id, manual, interactive=False, prompt=_refuse, confirm=_refuse) is None


# --- where the key comes from ---------------------------------------------------------------

def test_the_run_s_own_key_comes_first(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    assert ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True, "openrouterApiKey": "from-config"}},
                         interactive=False) == _openrouter("from-config")
    assert ensure_ai_key("instagram.engagement.coldDm", {"messageMode": "ai", "openrouterApiKey": "flat-key"},
                         interactive=False) == _openrouter("flat-key")
    assert ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True, "provider": "anthropic", "apiKey": ANTHROPIC_KEY}},
                         interactive=False) == AICredential(provider="anthropic", api_key=ANTHROPIC_KEY)


def test_the_environment_serves_when_the_run_brings_none(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", " from-env ")
    assert ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True}}, interactive=False,
                         prompt=_refuse) == _openrouter("from-env")


def test_an_anthropic_key_of_the_environment_serves_and_openrouter_comes_first(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", ANTHROPIC_KEY)
    assert ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True}}, interactive=False,
                         prompt=_refuse) == AICredential(provider="anthropic", api_key=ANTHROPIC_KEY)
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    assert resolve_cli_credential() == _openrouter("from-env")


def test_a_saved_key_serves_without_asking():
    user_config.write_user_setting(ai_key.SAVED_KEY_SETTINGS["openrouter"], "saved-key")
    assert ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True}}, interactive=False,
                         prompt=_refuse) == _openrouter("saved-key")
    assert resolve_cli_credential() == _openrouter("saved-key")


# --- no key ---------------------------------------------------------------------------------

def test_a_scripted_run_without_a_key_is_refused_with_how_to_give_it():
    with pytest.raises(MissingAIKeyError) as refused:
        ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True}}, interactive=False, prompt=_refuse)
    message = str(refused.value)
    assert "OPENROUTER_API_KEY" in message and "ANTHROPIC_API_KEY" in message
    assert "instagram.automation.feed" in message
    assert user_config.user_config_path() in message


def test_at_a_terminal_the_key_is_asked_hidden_and_saved_on_request():
    user_config.write_user_setting("api_url", "https://api.example.test")
    asked = []

    def prompt(text, **kwargs):
        asked.append(kwargs)
        return " typed-key "

    key = ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True}}, interactive=True, prompt=prompt,
                        confirm=lambda *a, **k: True, echo=lambda _m: None)

    assert key == _openrouter("typed-key")
    assert asked[0]["hide_input"] is True
    saved = json.loads(open(user_config.user_config_path(), encoding="utf-8").read())
    assert saved == {"api_url": "https://api.example.test", "openrouter_api_key": "typed-key"}


def test_a_typed_anthropic_key_is_kept_and_saved_as_one():
    key = ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True}}, interactive=True, prompt=lambda *a, **k: ANTHROPIC_KEY,
                        confirm=lambda *a, **k: True, echo=lambda _m: None)

    assert key == AICredential(provider="anthropic", api_key=ANTHROPIC_KEY)
    assert user_config.read_user_setting(ai_key.SAVED_KEY_SETTINGS["anthropic"]) == ANTHROPIC_KEY
    assert user_config.read_user_setting(ai_key.SAVED_KEY_SETTINGS["openrouter"]) is None


def test_a_key_typed_but_not_saved_serves_this_process_only():
    key = ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True}}, interactive=True, prompt=lambda *a, **k: "once-key",
                        confirm=lambda *a, **k: False, echo=lambda _m: None)

    assert key == _openrouter("once-key")
    assert resolve_cli_credential() == _openrouter("once-key")
    assert user_config.read_user_setting(ai_key.SAVED_KEY_SETTINGS["openrouter"]) is None


def test_an_empty_answer_is_a_refusal():
    with pytest.raises(MissingAIKeyError):
        ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True}}, interactive=True, prompt=lambda *a, **k: "",
                      confirm=_refuse, echo=lambda _m: None)


def test_a_scripted_run_or_ci_is_never_interactive(monkeypatch):
    assert is_interactive(scripted=True) is False
    monkeypatch.setenv("CI", "true")
    assert is_interactive() is False


def test_the_api_url_still_lives_in_the_same_file():
    from taktik.core.shared.config.api_endpoints import APIEndpointManager

    manager = APIEndpointManager()
    assert manager.save_api_url("https://api.example.test/") is True
    assert manager._load_from_config() == "https://api.example.test"
    user_config.write_user_setting(ai_key.SAVED_KEY_SETTINGS["openrouter"], "k")
    assert manager._load_from_config() == "https://api.example.test"


# --- the commands ---------------------------------------------------------------------------

def _connect_spy(monkeypatch):
    from taktik.cli.commands import workflows as workflow_cmds

    connected = []

    def choose_phone(device_id):
        connected.append(device_id)
        return None  # no phone in the test: the run stops there

    monkeypatch.setattr(workflow_cmds, "_choose_phone", choose_phone)
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
    assert result.exit_code == 1  # no device in the test: the run stops at the phone


def test_workflows_run_asks_at_a_terminal_and_saves(monkeypatch):
    workflow_cmds, connected = _connect_spy(monkeypatch)
    monkeypatch.setattr(workflow_cmds, "is_interactive", lambda scripted=False: not scripted)

    result = CliRunner().invoke(workflow_cmds.workflows, [
        "run", "tiktok.automation.for_you", "--param", "ai={\"enabled\": true}"], input="term-key\ny\n")

    assert "OpenRouter or Anthropic API key" in result.output
    assert "term-key" not in result.output
    assert connected == [None]
    assert user_config.read_user_setting(ai_key.SAVED_KEY_SETTINGS["openrouter"]) == "term-key"


def test_a_dry_run_says_whether_the_key_is_there_without_asking(monkeypatch):
    from taktik.cli.commands import workflows as workflow_cmds

    result = CliRunner().invoke(workflow_cmds.workflows, [
        "run", "instagram.automation.feed", "--dry-run", "--json", json.dumps({"ai": {"enabled": True}})])

    assert result.exit_code == 0
    assert "no AI key found" in result.output


def test_the_agent_handler_takes_the_cli_key_when_the_payload_has_none(monkeypatch):
    """`workflows run instagram.engagement.taktik_agent`: a typed or saved key reaches the Agent with
    its provider, which otherwise only looks at its config and the environment."""
    from taktik.core.kernel.contracts import WorkflowInvocation
    from taktik.core.social_media.instagram.workflows.agent import agent_handler

    seen = []
    monkeypatch.setattr(agent_handler, "run_instagram_agent",
                        lambda config, **_kwargs: seen.append(dict(config)) or {"success": True})
    handler = agent_handler.build_instagram_agent_handler(
        instagram_agent_runtime=lambda _package: agent_handler.AgentRuntime(device_manager=None, restart=lambda: True),
        instagram_ai_key=lambda: AICredential(provider="anthropic", api_key="cli-key"),
    )
    invocation = WorkflowInvocation(platform="instagram", workflow_id=agent_handler.INSTAGRAM_AGENT_WORKFLOW_ID,
                                    params={})

    handler(invocation, {})
    handler(invocation, {"openrouter_api_key": "desktop-key"})

    assert (seen[0]["ai_provider"], seen[0]["ai_api_key"]) == ("anthropic", "cli-key")
    assert "ai_api_key" not in seen[1] and seen[1]["openrouter_api_key"] == "desktop-key"


# --- the refusal is the engine's: its code, its rule, every door --------------------------------

def test_the_refusal_is_the_engines_missing_ai_key_and_says_so():
    """The same code as the app's launch gate and the catalogue of the bridges' expected refusals: a script
    reads it in the first words of the message."""
    from taktik.core.contract.error_codes import BRIDGE_ERROR_PHRASES, BRIDGE_REFUSAL_CODES

    with pytest.raises(MissingAIKeyError) as refused:
        ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True}}, interactive=False, prompt=_refuse)

    assert MissingAIKeyError.error_code == "missing_ai_key"
    assert "missing_ai_key" in BRIDGE_ERROR_PHRASES and "missing_ai_key" in BRIDGE_REFUSAL_CODES
    assert str(refused.value).startswith("missing_ai_key: ")


@pytest.mark.parametrize("brought", [
    pytest.param({"ai": {"enabled": True, "openrouterApiKey": "abc"}}, id="config-too-short"),
    pytest.param({"ai": {"enabled": True, "provider": "anthropic", "apiKey": "sk-an"}}, id="anthropic-too-short"),
])
def test_a_key_too_short_to_be_one_is_no_key(brought):
    """The AI service builds with a key longer than 5 characters only, and goes on without AI otherwise:
    a run that brings less is refused at the door, not run without the AI it asked for."""
    with pytest.raises(MissingAIKeyError):
        ensure_ai_key("instagram.automation.feed", brought, interactive=False, prompt=_refuse)


def test_a_key_too_short_in_the_environment_is_no_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "abc")

    with pytest.raises(MissingAIKeyError):
        ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True}}, interactive=False, prompt=_refuse)


def test_a_usable_key_of_the_environment_serves_when_the_run_brings_one_too_short(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", ANTHROPIC_KEY)

    assert ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True, "openrouterApiKey": "abc"}},
                         interactive=False, prompt=_refuse) == AICredential(provider="anthropic", api_key=ANTHROPIC_KEY)


def test_a_key_typed_too_short_is_a_refusal():
    with pytest.raises(MissingAIKeyError):
        ensure_ai_key("instagram.automation.feed", {"ai": {"enabled": True}}, interactive=True,
                      prompt=lambda *a, **k: "abc", confirm=_refuse, echo=lambda _m: None)


def test_the_automation_command_refuses_a_scripted_ai_run_without_a_key_as_workflows_run_does(monkeypatch, tmp_path):
    """`taktik automation workflow --config run.json`: the same cause, the same exit code and the same
    words as `taktik workflows run`, not a « Workflow failed » that exits 1."""
    from types import SimpleNamespace

    from taktik.cli.commands import workflows as workflow_cmds
    from taktik.cli.commands.instagram.automation import automation

    monkeypatch.setattr(workflow_cmds, "_choose_phone",
                        lambda _device: SimpleNamespace(device_id="emulator-5554", device_manager=object()))
    config = tmp_path / "run.json"
    config.write_text(json.dumps({"workflowType": "feed", "ai": {"enabled": True}}), encoding="utf-8")

    result = CliRunner().invoke(automation, ["workflow", "--config", str(config)])

    assert result.exit_code == MISSING_KEY_EXIT == 2, result.output
    assert "missing_ai_key" in result.output and "OPENROUTER_API_KEY" in result.output
    assert "Workflow failed" not in result.output


def _hosts_that_find_the_key_themselves():
    """What a CLI run asks of its host for the AI, mid-run, with the run's own key absent."""
    from taktik.cli.hosts import instagram as instagram_host
    from taktik.cli.hosts import tiktok as tiktok_host

    return [
        pytest.param(lambda: instagram_host.cli_instagram_ai_service({"enabled": True}), id="instagram-service"),
        pytest.param(ai_key.require_cli_credential, id="instagram-key"),
        pytest.param(lambda: tiktok_host.cli_tiktok_ai_hooks({"enabled": True}, "en"), id="tiktok-hooks"),
        pytest.param(lambda: tiktok_host.cli_tiktok_welcome_qualifier({"enabled": True}, "en"), id="tiktok-welcome"),
        pytest.param(lambda: tiktok_host.cli_tiktok_outreach_message_generator("Say hello", AICredential()),
                     id="tiktok-outreach"),
    ]


@pytest.mark.parametrize("ask", _hosts_that_find_the_key_themselves())
def test_a_host_that_finds_no_key_for_a_run_that_asks_refuses_it_instead_of_going_on_without_ai(ask):
    """Behind the door these are not reached; if the door's rule and a handler's ever disagree, the run is
    refused here, said, rather than run without the AI it asked for with a line in the log."""
    with pytest.raises(MissingAIKeyError) as refused:
        ask()

    assert str(refused.value).startswith("missing_ai_key: ")


def test_a_host_asked_for_nothing_gives_nothing_and_refuses_nothing():
    from taktik.cli.hosts import instagram as instagram_host
    from taktik.cli.hosts import tiktok as tiktok_host

    assert instagram_host.cli_instagram_ai_service({"enabled": False}) is None
    assert tiktok_host.cli_tiktok_ai_hooks({"enabled": False}, "en") is None
    assert tiktok_host.cli_tiktok_welcome_qualifier({}, "en") is None
