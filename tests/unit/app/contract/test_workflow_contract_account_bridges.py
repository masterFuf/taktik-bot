"""The account bridges read the file the contract describes and print the lines it declares.

The same proof as `test_workflow_contract_bridges.py`, for the four account bridges (Instagram,
TikTok, Gmail, YouTube): each bridge runs in full on the app's file for one flow, through the real
reader and the real launcher (`run_<platform>_account`); only the phone connection, the app
restart, the base and the flow's screen work are replaced. Each flow runs once to the end and once
failing: together, the two runs print every line the declaration names, and nothing else.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from contract_probe import Recording
from taktik.core.contract import accounts
from test_workflow_contract_bridges import assert_reads, bridge_file, check_lines, lines  # noqa: F401 (fixture)

_IG = "taktik.core.social_media.instagram.workflows.management.agent_handler"
_TT = "taktik.core.social_media.tiktok.workflows.management.agent_handler"
_GMAIL = "taktik.core.social_media.gmail.workflows.agent_handler"
_YOUTUBE = "taktik.core.social_media.youtube.workflows.account.agent_handler"


class _App:
    package = "com.example.app"

    def is_running(self) -> bool:
        return False

    def restart(self) -> bool:
        return True


class _Screen:
    """The screen work of every account flow, answering from a script; `fail` makes it raise."""

    fail = False

    def __init__(self, device, device_id, notifier=None, on_active_account=None, on_step=None, **_: Any):
        self.notifier = notifier
        self.on_active_account = on_active_account
        self.on_step = on_step

    def _done(self, **extra: Any) -> Dict[str, Any]:
        if self.fail:
            raise RuntimeError("the screen did not open")
        return {"success": True, "message": "done", "error_type": None, **extra}

    # Instagram and TikTok login, register, logout; Instagram language change.
    def execute(self, target: str = "", **params: Any) -> Dict[str, Any]:
        if target:
            return self._switch(target)
        if "language" in params:
            self.notifier(step="select_language", status="done", message="set", language=params["language"],
                          native_name="Native")
            return self._done(language=params["language"], native_name="Native", app_restarted=True)
        return self._done(step="done")

    def _walk_picker(self) -> None:
        self.notifier("Reading the picker")
        self.on_active_account("alice")
        self.on_step("enumerate", {"accounts": ["alice", "bob"]})
        self.on_step("select", {"username": "bob"})

    def _switch(self, target: str) -> Dict[str, Any]:
        self._walk_picker()
        return self._done(switched_to=target, relogin_required=False, detected_accounts=["alice", "bob"])

    def list_accounts(self) -> Dict[str, Any]:
        self._walk_picker()
        return self._done(accounts=["alice", "bob"])

    list_saved_accounts = list_accounts

    # TikTok language change.
    def run(self, target: str) -> Dict[str, Any]:
        return self._done(language_before="en", language_after=target, already_set=False)

    # Gmail.
    def ensure_account_added(self, **params: Any) -> Dict[str, Any]:
        return self._done()

    open_account_removal_settings = ensure_account_added

    def get_latest_verification_code(self, **params: Any) -> Dict[str, Any]:
        return self._done(code="123456")

    def scan_accounts(self) -> Dict[str, Any]:
        return self._done(accounts=[{"name": None, "email": "someone@example.com", "is_active": True}])

    # YouTube: a failure is a result, not an exception.
    def login(self, **params: Any) -> Dict[str, Any]:
        if self.fail:
            return {"success": False, "message": "not signed in", "error_type": "picker_not_found"}
        return self._done()

    logout = login


@pytest.fixture
def phone(monkeypatch):
    """What the account bridges touch before the flow: the base, the connection, the app restart."""
    import taktik.core.database as database

    monkeypatch.setattr(database, "configure_db_service", lambda *a, **k: None)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    connection = SimpleNamespace(connect=lambda: True, device=object())
    session = SimpleNamespace(connection=connection, device=connection.device)
    for name in ("bridges.instagram.account.session", "bridges.tiktok.account.account_session"):
        module = importlib.import_module(name)
        monkeypatch.setattr(module, "ConnectionService", lambda device_id: connection)
        monkeypatch.setattr(module, "AppService", lambda *a, **k: _App())
    monkeypatch.setattr(f"{_TT}.patch_clone_selectors", lambda *a: None)
    for name, prefix in (("bridges.gmail.account.gmail_account_bridge", "gmail"), ("bridges.youtube.account.youtube_account_bridge", "youtube")):
        module = importlib.import_module(name)
        monkeypatch.setattr(module, f"prepare_{prefix}_session", lambda *a: session)
        monkeypatch.setattr(module, f"cleanup_{prefix}_app", lambda device_id: None)
    for name in ("workflow_login", "workflow_scan"):
        monkeypatch.setattr(f"bridges.gmail.account.{name}.persist_gmail_account", lambda *a: None)
    monkeypatch.setattr("bridges.gmail.account.workflow_logout.unpersist_gmail_account", lambda *a: None)

    launchers = {
        _IG: ("run_instagram_account", ("login_workflow_factory", "logout_workflow_factory",
                                        "signup_workflow_factory", "change_language_workflow_factory",
                                        "switch_workflow_factory")),
        _TT: ("run_tiktok_account", ("login_workflow_factory", "logout_workflow_factory",
                                     "signup_workflow_factory", "change_language_workflow_factory")),
        _GMAIL: ("run_gmail_account", ("workflow_factory",)),
        _YOUTUBE: ("run_youtube_account", ("workflow_factory",)),
    }
    for module, (launcher, factories) in launchers.items():
        defaults = getattr(importlib.import_module(module), launcher).__kwdefaults__
        for factory in factories:
            monkeypatch.setitem(defaults, factory, _Screen)


def _bridge(contract):
    return {
        "account_bridge": ("bridges.instagram.account.bridge", "AccountBridge"),
        "tiktok_account_bridge": ("bridges.tiktok.account.bridge", "TikTokAccountBridge"),
        "gmail_account_bridge": ("bridges.gmail.account.gmail_account_bridge", "GmailAccountBridge"),
        "youtube_account_bridge": ("bridges.youtube.account.youtube_account_bridge", "YouTubeAccountBridge"),
    }[contract.bridge]


@pytest.mark.parametrize("contract", [pytest.param(c, id=c.workflow_id) for c in accounts.CONTRACTS])
def test_the_account_bridges_follow_their_contract(monkeypatch, lines, phone, contract):
    module, name = _bridge(contract)
    bridge_class = getattr(importlib.import_module(module), name)
    printed = set()
    for fail in (False, True):
        monkeypatch.setattr(_Screen, "fail", fail)
        data = bridge_file(contract)
        log: set = set()
        lines.clear()

        assert bridge_class(Recording(data, log)).run() == (1 if fail else 0)

        assert_reads(contract, data, log)
        check_lines(contract, lines)
        printed |= {line["type"] for line in lines}

    assert printed == {event.type for event in contract.events}


@pytest.mark.parametrize("contract", [pytest.param(c, id=c.workflow_id) for c in accounts.CONTRACTS if c.refusals])
def test_an_account_bridge_refuses_a_file_before_the_flow(monkeypatch, lines, phone, contract):
    module, name = _bridge(contract)
    started = []
    monkeypatch.setattr(_Screen, "__init__", lambda self, *a, **k: started.append(True))
    data = bridge_file(contract)
    for name_ in contract.setting(contract.refusals[0].missing).names:
        data.pop(name_, None)

    assert getattr(importlib.import_module(module), name)(data).run() == 1

    assert not started
    assert "error" in {line["type"] for line in lines}
    check_lines(contract, lines)


def test_every_account_flow_of_the_manifest_is_declared():
    import json
    from pathlib import Path

    manifest = json.loads((Path(__file__).resolve().parents[4] / "workflows.manifest.json").read_text(encoding="utf-8-sig"))
    ids = {f"{platform}.account.{flow}" for platform in ("instagram", "tiktok", "gmail", "youtube")
           for flow in manifest[platform]["account"]}

    assert ids == {contract.workflow_id for contract in accounts.CONTRACTS}
    assert all(contract.bridge_fields[0].key == "deviceId" for contract in accounts.CONTRACTS)
