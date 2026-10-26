"""Each run of the CLI starts clean, whatever the run before it in the same process left.

The interactive menu serves one run after another in one process, and nothing lifted the stop latch
between two of them: a run whose phone lost its network (`network_lost`) or met Instagram's « Try
again later » left the latch set, and the next run of the menu stopped before its first gesture,
under the motive of the run before. The network watch of the first run went on pinging the phone
while the menu waited, and could set the latch for a run that had not started.

Every door of the CLI that runs a workflow runs it inside `run_scope()`
(`taktik/core/shared/diagnostics/run_start.py`), as the bridges' entry and the Lab session do: the run
begins clean (`begin_run`) and its watch stops when it ends (`end_run`). Each door is played twice
here, by its real code down to the workflow it calls: the first run sets the latch and leaves its
watch running; no watch may be left once it has ended, and the second run must start without either.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from taktik.cli.commands import workflows as workflow_cmds
from taktik.cli.commands.instagram import agent as agent_cmds
from taktik.cli.commands.instagram import publish as publish_cmds
from taktik.cli.hosts import ai_key
from taktik.cli.hosts import instagram as instagram_host
from taktik.cli.hosts import registry as cli_registry
from taktik.cli.hosts.phone import CliPhone
from taktik.cli.menus import registry as registry_menu
from taktik.core.social_media.instagram.workflows.agent import agent_handler as agent_launcher
from taktik.core.social_media.instagram.workflows.publish import agent_handler as publish_launcher
from unit.previous_run import CLEAN, SERIAL, RunThatLosesItsNetwork, watches_alive


class _ConnectedManager:
    """The CLI's `DeviceManager`, already connected (a menu connects its phone before it runs)."""

    device = object()

    def connect(self, device_id=None, verify_atx=True):
        return True


def _phone(_device_id=None) -> CliPhone:
    return CliPhone(_ConnectedManager(), SERIAL)


def _menu_automation(monkeypatch, tmp_path, run):
    # The main menu's automation, cold DM, scraping and account entries: `_run_through_handler`.
    monkeypatch.setattr(ai_key, "ensure_ai_key", lambda *a, **k: None)
    monkeypatch.setattr(cli_registry, "build_registry", lambda **kwargs: None)
    monkeypatch.setattr(cli_registry, "handler_on_phone", lambda build, workflow_id, phone: run)
    instagram_host.run_instagram_payload(_ConnectedManager(), SERIAL, {"workflowType": "target_profiles"})


def _menu_registry(monkeypatch, tmp_path, run):
    # The TikTok, Threads, Gmail and YouTube entries of the main menu: the registry menu.
    build = SimpleNamespace(failures=[], ids_for=lambda platform: ["tiktok.automation.for_you"],
                            registry=SimpleNamespace(resolve=lambda workflow_id: run))
    monkeypatch.setattr(registry_menu, "build_registry", lambda **kwargs: build)
    monkeypatch.setattr(registry_menu, "ensure_ai_key", lambda *a, **k: None)
    # The first entry, then an empty parameter line.
    monkeypatch.setattr(registry_menu.click, "prompt", lambda text, **k: "" if "param" in str(text) else 1)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    registry_menu.run_registry_menu("tiktok", _ConnectedManager(), SERIAL)


def _menu_publish(monkeypatch, tmp_path, run):
    # The main menu's publish entry, which runs the `publish` command's code.
    image = tmp_path / "post.jpg"
    image.write_bytes(b"\xff\xd8\xff")
    monkeypatch.setattr(workflow_cmds, "_choose_phone", _phone)
    monkeypatch.setattr(publish_launcher, "run_instagram_publish", run)
    assert publish_cmds.run_publish("post", SERIAL, (str(image),)) is True


def _command_workflows_run(monkeypatch, tmp_path, run):
    build = SimpleNamespace(registry=SimpleNamespace(resolve=lambda workflow_id: run))
    monkeypatch.setattr(workflow_cmds, "_choose_phone", _phone)
    monkeypatch.setattr(workflow_cmds, "build_registry", lambda **kwargs: build)
    monkeypatch.setattr(workflow_cmds, "handler_on_phone", lambda build, workflow_id, phone: run)
    monkeypatch.setattr(workflow_cmds, "ensure_ai_key", lambda *a, **k: None)
    result = CliRunner().invoke(workflow_cmds.workflows, ["run", "tiktok.automation.for_you", "--device", SERIAL])
    assert result.exit_code == 0, result.output


def _command_agent_run(monkeypatch, tmp_path, run):
    monkeypatch.setattr(workflow_cmds, "_choose_phone", _phone)
    monkeypatch.setattr(agent_cmds, "ensure_ai_key", lambda *a, **k: None)
    monkeypatch.setattr(agent_launcher, "run_instagram_agent", run)
    result = CliRunner().invoke(agent_cmds.agent, ["run", "--device", SERIAL])
    assert result.exit_code == 0, result.output


DOORS = {
    "menu: automation, cold DM, scraping, account (_run_through_handler)": _menu_automation,
    "menu: TikTok and the other platforms (run_registry_menu)": _menu_registry,
    "menu: publish (run_publish)": _menu_publish,
    "taktik workflows run": _command_workflows_run,
    "taktik agent run": _command_agent_run,
}


@pytest.mark.parametrize("door", list(DOORS.values()), ids=list(DOORS))
def test_the_second_run_of_a_door_starts_without_what_the_first_left(door, monkeypatch, tmp_path):
    run = RunThatLosesItsNetwork(monkeypatch)

    door(monkeypatch, tmp_path, run)
    door(monkeypatch, tmp_path, run)

    assert run.started_with == [CLEAN, CLEAN]


@pytest.mark.parametrize("door", list(DOORS.values()), ids=list(DOORS))
def test_no_watch_pings_the_phone_once_a_run_of_a_door_has_ended(door, monkeypatch, tmp_path):
    # The menu waits for the operator between two runs: nothing measures the phone meanwhile.
    run = RunThatLosesItsNetwork(monkeypatch)

    door(monkeypatch, tmp_path, run)

    assert watches_alive() == []
