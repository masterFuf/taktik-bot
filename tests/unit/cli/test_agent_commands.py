"""The Agent must be startable without the desktop app.

`TaktikAgentWorkflow` lives in `taktik/core/agent/`, takes its device manager and config by
injection, and treats the notifier as optional — nothing about it required a bridge. Yet its
desktop bridge was the only caller, so a standalone user could not start the bot's autonomous
path at all.

The test that matters most here is the quota one: the CLI advertises defaults, and an advertised
default that has drifted from the workflow is worse than none.
"""
import re
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from taktik.cli.commands import agent_cmds


def test_advertised_quotas_match_the_workflow():
    """`agent defaults` must not describe numbers the workflow no longer uses."""
    source = Path(
        "taktik/core/agent/scenarios/instagram_feed_autopilot.py"
    ).read_text(encoding="utf-8")

    for key, advertised in agent_cmds.QUOTA_DEFAULTS.items():
        match = re.search(rf'config\.get\(\s*"{key}"\s*,\s*(\d+)\s*\)', source)
        assert match, f"{key} is advertised by the CLI but not read by the workflow"
        assert int(match.group(1)) == advertised, (
            f"{key}: CLI advertises {advertised}, workflow defaults to {match.group(1)}"
        )


def test_defaults_command_lists_every_quota():
    result = CliRunner().invoke(agent_cmds.agent, ["defaults"])
    assert result.exit_code == 0
    for key in agent_cmds.QUOTA_DEFAULTS:
        assert key in result.output


def test_the_cli_does_not_import_a_bridge():
    """A module outside bridges/ must not depend on one; the AI provider comes from core."""
    source = Path("taktik/cli/commands/agent_cmds.py").read_text(encoding="utf-8")
    assert "bridges" not in source.replace("bridges/", "")  # the word only appears in prose
    assert "taktik.core.app.ai.providers.openrouter" in source


def test_a_malformed_param_is_refused(monkeypatch):
    result = CliRunner().invoke(agent_cmds.agent, ["run", "--param", "no_equals"])
    assert result.exit_code != 0
    assert "key=value" in result.output


def test_no_device_is_reported_not_crashed(monkeypatch):
    class NoDevices:
        def list_devices(self):
            return []

    with patch("taktik.core.shared.device.manager.DeviceManager", NoDevices):
        result = CliRunner().invoke(agent_cmds.agent, ["run"])
    assert result.exit_code == 1
    assert "No device connected" in result.output


def test_the_notifier_absorbs_unknown_events():
    """The workflow may call helpers this stand-in does not implement; that must not stop a run."""
    notifier = agent_cmds._ConsoleNotifier()
    notifier.some_event_helper_that_does_not_exist(1, key="value")
    notifier.status("running", "ok")


def test_the_api_key_is_read_from_the_environment_only():
    """A key passed as a flag would land in shell history and in the process list."""
    source = Path("taktik/cli/commands/agent_cmds.py").read_text(encoding="utf-8")
    assert "os.environ.get(API_KEY_ENV" in source
    assert "--api-key" not in source
