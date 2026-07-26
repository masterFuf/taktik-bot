"""The interactive menu must offer what the registry holds, and nothing invented.

TikTok's menu was nine "Coming soon" entries — one of them stating the workflows were not
implemented yet — while fifteen TikTok workflows ran in production from the desktop app. The
entries were hand-written, so they described the menu's own history rather than the bot's
capabilities.

The menu is now generated from the registry. These tests pin that: the listing matches the
registry, the chosen workflow is the one invoked, and a failing workflow reports instead of
raising at the operator.
"""
from unittest.mock import patch

import pytest

from taktik.cli.common import registry_menu
from taktik.cli.common.registry_builder import build_registry


class FakeDeviceManager:
    device = object()

    def connect(self, device_id):  # pragma: no cover - not exercised here
        return True


@pytest.fixture
def answers(monkeypatch):
    """Feed click.prompt and input() a scripted sequence."""
    def _install(prompt_values, param_lines=()):
        prompts = list(prompt_values)
        params = list(param_lines) + [""]

        def fake_prompt(text, **kwargs):
            if "param" in str(text):
                return params.pop(0) if params else ""
            return prompts.pop(0)

        monkeypatch.setattr(registry_menu.click, "prompt", fake_prompt)
        monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    return _install


def test_menu_lists_exactly_what_the_registry_holds(answers, capsys):
    build = build_registry(device=None, device_id="")
    expected = build.ids_for("tiktok")
    assert expected, "precondition: tiktok must have registered workflows"

    answers([len(expected) + 1])  # pick "Back"
    registry_menu.run_registry_menu("tiktok", FakeDeviceManager(), "dev-1")

    output = capsys.readouterr().out
    for workflow_id in expected:
        assert workflow_id in output, workflow_id


def test_choosing_an_entry_invokes_that_workflow(answers, capsys):
    build = build_registry(device=None, device_id="")
    first = build.ids_for("tiktok")[0]
    seen = {}

    def fake_handler(invocation, payload):
        seen["workflow_id"] = invocation.workflow_id
        seen["platform"] = invocation.platform
        seen["params"] = payload
        return {"success": True, "processed": 3}

    answers([1], param_lines=["max_videos=7"])
    with patch.object(registry_menu, "build_registry") as fake_build:
        fake_build.return_value = build
        with patch.object(build.registry, "resolve", return_value=fake_handler):
            registry_menu.run_registry_menu("tiktok", FakeDeviceManager(), "dev-1")

    assert seen["workflow_id"] == first
    assert seen["platform"] == "tiktok"
    assert seen["params"] == {"max_videos": 7}, "params must be typed, not left as strings"
    assert "Done." in capsys.readouterr().out


def test_a_failing_workflow_is_reported_not_raised(answers, capsys):
    build = build_registry(device=None, device_id="")

    def boom(invocation, payload):
        raise RuntimeError("device went away")

    answers([1])
    with patch.object(registry_menu, "build_registry") as fake_build:
        fake_build.return_value = build
        with patch.object(build.registry, "resolve", return_value=boom):
            registry_menu.run_registry_menu("tiktok", FakeDeviceManager(), "dev-1")

    output = capsys.readouterr().out
    assert "Workflow failed" in output and "device went away" in output


def test_an_unknown_platform_says_so_instead_of_showing_an_empty_menu(answers, capsys):
    answers([])
    registry_menu.run_registry_menu("myspace", FakeDeviceManager(), "dev-1")
    assert "No workflow registered" in capsys.readouterr().out


def test_result_false_is_surfaced_as_a_failure(answers, capsys):
    build = build_registry(device=None, device_id="")

    answers([1])
    with patch.object(registry_menu, "build_registry") as fake_build:
        fake_build.return_value = build
        with patch.object(build.registry, "resolve",
                          return_value=lambda i, p: {"success": False, "error": "no session"}):
            registry_menu.run_registry_menu("tiktok", FakeDeviceManager(), "dev-1")

    assert "no session" in capsys.readouterr().out
