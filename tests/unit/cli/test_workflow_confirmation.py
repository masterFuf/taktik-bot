"""A workflow that logs the account out runs from the CLI only once the operator said yes.

`instagram.account.list_saved_accounts` reads like a list and logs the account out: the only
screen that shows every saved account is the logged-out picker. From a terminal it ran at once.
It now warns, asks at a terminal, and in a script needs `--yes`; the phone is not touched before.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from taktik.cli.commands import workflows as workflow_cmds
from taktik.cli.commands.workflows import workflows

LOGS_OUT = "instagram.account.list_saved_accounts"


@pytest.fixture
def connections(monkeypatch):
    calls = []

    def _connect(device_id):
        calls.append(device_id)
        return None, ""  # no phone: the command stops right after

    monkeypatch.setattr(workflow_cmds, "_connect", _connect)
    return calls


def test_a_script_without_yes_is_refused_before_the_phone(connections):
    result = CliRunner().invoke(workflows, ["run", LOGS_OUT])

    assert result.exit_code != 0
    assert connections == []
    assert "--yes" in result.output
    assert "log" in result.output.lower()


def test_with_yes_it_goes_to_the_phone(connections):
    CliRunner().invoke(workflows, ["run", LOGS_OUT, "--yes"])

    assert connections == [None]


def test_at_a_terminal_a_no_stops_it(connections, monkeypatch):
    monkeypatch.setattr(workflow_cmds, "is_interactive", lambda scripted=False: True)
    monkeypatch.setattr(workflow_cmds.Confirm, "ask", staticmethod(lambda *a, **k: False))

    result = CliRunner().invoke(workflows, ["run", LOGS_OUT])

    assert result.exit_code != 0
    assert connections == []


def test_at_a_terminal_a_yes_goes_on(connections, monkeypatch):
    monkeypatch.setattr(workflow_cmds, "is_interactive", lambda scripted=False: True)
    monkeypatch.setattr(workflow_cmds.Confirm, "ask", staticmethod(lambda *a, **k: True))

    CliRunner().invoke(workflows, ["run", LOGS_OUT])

    assert connections == [None]


def test_a_workflow_that_keeps_the_account_asks_nothing(connections):
    CliRunner().invoke(workflows, ["run", "instagram.account.list_accounts"])

    assert connections == [None]


def test_the_dry_run_says_it_logs_out(connections):
    result = CliRunner().invoke(workflows, ["run", LOGS_OUT, "--dry-run"])

    assert result.exit_code == 0
    assert "log" in result.output.lower()
    assert connections == []
