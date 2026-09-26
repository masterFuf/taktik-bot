"""The notifications bridge reads its command from a config file, like the other bridges.

It used to take positional arguments plus eight flags (`--account`, `--package`, the three daily
caps, `--follow-suggestions`, `--ai-config`, `--language`), parsed by hand: a value the desktop
sent that the bridge did not know was silently dropped, and the app's config contract test could
not follow the settings to the bot. The frozen sequence (`one_path/`) proves no gesture moved; these
tests pin how the file is read and refused. The command is read by the core launcher,
`run_instagram_notifications`, which hands each command the host (connection, events) first;
the package is the bridge's own, read when it connects.
"""
import io
import json
import sys

import pytest

import bridges.instagram.engagement.runtime.notifications.commands as bridge_commands
import taktik.core.social_media.instagram.workflows.management.notifications.commands as commands


@pytest.fixture
def run(monkeypatch, tmp_path):
    calls = []
    for name in ("cmd_scan", "cmd_list_requests", "cmd_accept_all", "cmd_reply", "cmd_batch",
                 "cmd_accept", "cmd_ignore", "cmd_like", "cmd_follow_back"):
        monkeypatch.setattr(commands, name, lambda _host, *a, _n=name, **k: calls.append((_n, a, k)))
    monkeypatch.setitem(commands.ROW_ACTIONS, "accept", commands.cmd_accept)
    monkeypatch.setitem(commands.ROW_ACTIONS, "ignore", commands.cmd_ignore)
    monkeypatch.setitem(commands.ROW_ACTIONS, "like", commands.cmd_like)
    monkeypatch.setitem(commands.ROW_ACTIONS, "follow_back", commands.cmd_follow_back)

    def _run(config=None, *, raw=None, args=None):
        if args is None:
            path = tmp_path / "notif.json"
            path.write_text(raw if raw is not None else json.dumps(config), encoding="utf-8")
            args = [str(path)]
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        code = 0
        try:
            bridge_commands.run_notifications_cli(args)
        except SystemExit as exit_info:
            code = exit_info.code
        finally:
            monkeypatch.setattr(sys, "stdout", sys.__stdout__)
        lines = [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]
        return code, lines, calls

    return _run


def test_a_scan_takes_every_setting_from_the_file(run):
    code, _, calls = run({"command": "scan", "deviceId": "dev", "scroll": 2, "accountUsername": "me",
                          "packageName": "clone.pkg", "followSuggestions": 4,
                          "ai": {"enabled": True}, "language": "fr"})
    assert code == 0
    assert calls == [("cmd_scan", (2,), {
        "follow_suggestions": 4, "account_username": "me",
        "ai_config": {"enabled": True}, "language": "fr"})]


def test_a_scan_without_settings_keeps_the_defaults(run):
    _, _, calls = run({"command": "scan", "deviceId": "dev"})
    assert calls == [("cmd_scan", (3,), {
        "follow_suggestions": 0, "account_username": None,
        "ai_config": None, "language": "en"})]


def test_a_batch_reads_its_caps_and_its_source(run):
    actions = [{"action": "like", "username": "a"}]
    _, _, calls = run({"command": "batch", "deviceId": "dev", "actions": actions, "source": "autopilot",
                       "followBackDailyCap": -3, "welcomeDmDailyCap": "x", "followActorDailyCap": 2})
    assert calls == [("cmd_batch", (actions,), {
        "account_username": None, "source": "autopilot",
        "follow_back_daily_cap": 0, "welcome_dm_daily_cap": None, "follow_actor_daily_cap": 2})]


@pytest.mark.parametrize("command,target", [
    ("accept", "cmd_accept"), ("ignore", "cmd_ignore"), ("like", "cmd_like"), ("follow_back", "cmd_follow_back"),
])
def test_a_row_action_goes_to_its_verb(run, command, target):
    _, _, calls = run({"command": command, "deviceId": "dev", "username": "u", "accountUsername": "me"})
    assert calls == [(target, ("u",), {"account_username": "me"})]


def test_the_counts_of_list_requests_and_accept_all(run):
    run({"command": "list_requests", "deviceId": "dev", "limit": 20})
    _, _, calls = run({"command": "accept_all", "deviceId": "dev", "max": 7})
    assert calls[0] == ("cmd_list_requests", (20,), {})
    assert calls[1][0:2] == ("cmd_accept_all", (7,))


@pytest.mark.parametrize("config,error", [
    ({"command": "scan"}, "deviceId is required"),
    ({"command": "like", "deviceId": "dev"}, "username is required for like"),
    ({"command": "reply", "deviceId": "dev"}, "username is required for reply"),
    ({"command": "batch", "deviceId": "dev", "actions": []}, "Batch actions must be a non-empty list"),
    ({"command": "dance", "deviceId": "dev"}, "Unknown command: dance"),
])
def test_an_incomplete_command_is_refused_before_the_phone(run, config, error):
    code, lines, calls = run(config)
    assert code == 1
    assert lines == [{"success": False, "error": error}]
    assert calls == []


def test_a_file_that_is_not_an_object_is_refused(run):
    code, lines, _ = run(raw="[1, 2]")
    assert code == 1
    assert lines == [{"success": False, "error": "The notifications config must be a JSON object"}]


def test_an_unreadable_file_is_refused(run, tmp_path):
    code, lines, _ = run(args=[str(tmp_path / "missing.json")])
    assert code == 1
    assert lines[0]["error"].startswith("Failed to load config")


def test_no_file_is_a_usage_error(run):
    code, lines, _ = run(args=[])
    assert code == 1
    assert lines == [{"success": False, "error": "Usage: notifications_bridge <config.json>"}]
