"""A switch that lands on the password screen did not switch: it is a failure, said as such.

When the target account is on the picker but its session is not saved, Instagram asks for the
password. The switch used to report `success=True` with `relogin_required=True`: the page read the
flag and offered Login, but a scheduled `instagram-account` node (and a CLI run) took the success
at its word, and the next node of the plan ran on the password screen. The run is now a failure
(`error_type="relogin_required"`) that still carries the flag and the account, so the page keeps
its Login offer and the scheduler's journal says why the node failed.

The screen reads are the switcher's own methods, answered from a script: this tests what the
switch concludes from them, not a screen.
"""

from __future__ import annotations

import pytest

import taktik.core.social_media.instagram.auth.switch as switch_mod
from taktik.core.social_media.instagram.auth.switch import InstagramSwitchAccount
from taktik.core.social_media.instagram.workflows.management.switch.switch_workflow import (
    SwitchAccountWorkflow,
)


@pytest.fixture
def switcher(monkeypatch):
    monkeypatch.setattr(switch_mod.time, "sleep", lambda *_: None)
    steps = []
    manager = InstagramSwitchAccount(object(), "device-1", on_step=lambda step, data: steps.append(step))
    monkeypatch.setattr(manager, "_list_accounts_on_screen", lambda: ["account.one", "account.two"])
    monkeypatch.setattr(manager, "_select_account", lambda target: True)
    monkeypatch.setattr(manager, "_password_required", lambda: True)
    manager.steps = steps
    return manager


def _assert_relogin_failure(result) -> None:
    assert result.success is False
    assert result.error_type == "relogin_required"
    assert result.relogin_required is True
    assert result.switched_to == "account.two"
    assert result.detected_accounts == ["account.one", "account.two"]


def test_the_landing_picker_asking_for_the_password_is_a_failure(switcher, monkeypatch):
    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: True)

    _assert_relogin_failure(switcher.switch_to("account.two"))
    assert switcher.steps[-1] == "relogin"


def test_the_picker_after_logout_asking_for_the_password_is_a_failure(switcher, monkeypatch):
    monkeypatch.setattr(switcher, "_on_landing_account_list", lambda: False)
    monkeypatch.setattr(switcher, "detect_active_account", lambda: "account.one")
    monkeypatch.setattr(switcher._logout, "_open_profile_tab", lambda: True)
    monkeypatch.setattr(switcher._logout, "_open_options_menu", lambda: True)
    monkeypatch.setattr(switcher._logout, "_find_and_click_logout", lambda: True)
    monkeypatch.setattr(switcher._logout, "_confirm_logout", lambda: True)
    monkeypatch.setattr(switcher, "_ensure_on_picker", lambda: True)

    _assert_relogin_failure(switcher.switch_to("account.two"))
    assert switcher.steps[-1] == "relogin"


def test_the_workflow_result_the_bridge_prints_is_a_failure(monkeypatch):
    """What `account_result` carries: the app's node fails on it, the page reads the flag."""
    monkeypatch.setattr(switch_mod.time, "sleep", lambda *_: None)
    workflow = SwitchAccountWorkflow(object(), "device-1")
    manager = workflow.switch_manager
    monkeypatch.setattr(manager, "_on_landing_account_list", lambda: True)
    monkeypatch.setattr(manager, "_list_accounts_on_screen", lambda: ["account.two"])
    monkeypatch.setattr(manager, "_select_account", lambda target: True)
    monkeypatch.setattr(manager, "_password_required", lambda: True)

    result = workflow.execute("account.two")

    assert result["success"] is False
    assert result["error_type"] == "relogin_required"
    assert result["relogin_required"] is True
    assert result["switched_to"] == "account.two"
    assert "re-login" in result["message"]
