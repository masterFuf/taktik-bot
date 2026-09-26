"""Instagram and TikTok accounts: the bridge and the CLI reach the workflow through one launcher.

The account bridges used to build `LoginWorkflow`, `ChangeLanguageWorkflow`, `SwitchAccountWorkflow`
and their TikTok peers themselves, next to handlers that built them too (or none, for the language
change); `taktik auth login` built `LoginWorkflow` on a warm app. Each host still reads its own
payload and emits its own events; the start of the app and the workflow call are made in one
place, `run_instagram_account` / `run_tiktok_account`.
"""
from __future__ import annotations

import pytest
from click.testing import CliRunner

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowRegistry

DEVICE = object()
DEVICE_ID = "emulator-5554"

INSTAGRAM_BRIDGE_TYPES = (
    "login", "register", "logout", "change_language",
    "switch_account", "list_accounts", "list_saved_accounts",
)
TIKTOK_BRIDGE_TYPES = ("login", "register", "logout", "change_language")


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)


class FakeApp:
    def __init__(self, calls, *, running=False, package="com.instagram.android"):
        self.calls = calls
        self.running = running
        self.package = package

    def is_running(self):
        self.calls.append(("is_running",))
        return self.running

    def restart(self):
        self.calls.append(("restart",))
        return True


def _instagram_factories(calls):
    class Login:
        def __init__(self, device, device_id):
            calls.append(("built", "login", device is DEVICE, device_id))

        def execute(self, **params):
            calls.append(("login", tuple(sorted(params.items()))))
            return {"success": True, "message": "ok", "username": params["username"]}

    class Language:
        def __init__(self, device, device_id, notifier=None):
            calls.append(("built", "change_language", device is DEVICE, device_id))

        def execute(self, *, language):
            calls.append(("change_language", language))
            return {"success": True, "message": "ok", "native_name": "Français", "app_restarted": True}

    class Switch:
        def __init__(self, device, device_id, notifier=None, on_active_account=None, on_step=None):
            calls.append(("built", "switch", device is DEVICE, device_id))

        def execute(self, target):
            calls.append(("switch_account", target))
            return {"success": True, "message": "ok", "switched_to": target, "detected_accounts": []}

        def list_accounts(self):
            calls.append(("list_accounts",))
            return {"success": True, "message": "0", "accounts": []}

    return {
        "login_workflow_factory": Login,
        "change_language_workflow_factory": Language,
        "switch_workflow_factory": Switch,
    }


def _instagram_bridge(config, app):
    from bridges.instagram.account.runtime.bridge import AccountBridge

    bridge = AccountBridge.__new__(AccountBridge)  # no signal handlers in a test process
    bridge.config = {"deviceId": DEVICE_ID, **config}
    bridge.device_id = DEVICE_ID
    bridge.workflow_type = config["workflowType"]
    bridge.package_name = None
    bridge._app = app
    return bridge


def _instagram_cli(workflow_id, params, app, factories):
    from taktik.core.social_media.instagram.workflows.management.agent_handler import (
        register_instagram_account_handlers,
    )

    registry = WorkflowRegistry()
    register_instagram_account_handlers(registry, device=DEVICE, device_id=DEVICE_ID,
                                        instagram_account_app=lambda _package: app, **factories)
    invocation = WorkflowInvocation(platform="instagram", workflow_id=workflow_id, params=params)
    return registry.resolve(workflow_id)(invocation, {"deviceId": DEVICE_ID})


def _bridge_uses(monkeypatch, run, factories):
    for name, factory in factories.items():
        monkeypatch.setitem(run.__kwdefaults__, name, factory)


# --------------------------------------------------------------------------- Instagram


def test_every_instagram_account_flow_of_the_bridge_is_declared_and_launched():
    from taktik.core.agent import load_workflow_manifest
    from taktik.core.social_media.instagram.workflows.management.agent_handler import (
        register_instagram_account_handlers,
    )

    registry = WorkflowRegistry()
    register_instagram_account_handlers(registry, device=DEVICE, device_id=DEVICE_ID)
    manifest = load_workflow_manifest()
    for workflow_type in INSTAGRAM_BRIDGE_TYPES:
        assert manifest.contains(f"instagram.account.{workflow_type}")
        assert registry.resolve(f"instagram.account.{workflow_type}")


def test_instagram_login_is_the_same_call_from_the_bridge_and_the_cli(monkeypatch):
    from taktik.core.social_media.instagram.workflows.management import agent_handler

    page = {"username": "alice", "password": "pw", "saveSession": False, "saveLoginInfoInstagram": True}
    bridge_calls, cli_calls = [], []
    _bridge_uses(monkeypatch, agent_handler.run_instagram_account, _instagram_factories(bridge_calls))
    exit_code = _instagram_bridge({"workflowType": "login", **page}, FakeApp(bridge_calls))._run_login(DEVICE)
    _instagram_cli("instagram.account.login", page, FakeApp(cli_calls), _instagram_factories(cli_calls))

    assert exit_code == 0
    assert bridge_calls == cli_calls
    assert bridge_calls[0] == ("restart",)
    assert bridge_calls[1] == ("built", "login", True, DEVICE_ID)


def test_instagram_language_change_is_the_same_call_from_the_bridge_and_the_cli(monkeypatch):
    from taktik.core.social_media.instagram.workflows.management import agent_handler

    bridge_calls, cli_calls = [], []
    _bridge_uses(monkeypatch, agent_handler.run_instagram_account, _instagram_factories(bridge_calls))
    exit_code = _instagram_bridge({"workflowType": "change_language", "language": "fr"},
                                  FakeApp(bridge_calls))._run_change_language(DEVICE)
    _instagram_cli("instagram.account.change_language", {"language": "fr"}, FakeApp(cli_calls),
                   _instagram_factories(cli_calls))

    assert exit_code == 0
    assert bridge_calls == cli_calls == [
        ("restart",), ("built", "change_language", True, DEVICE_ID), ("change_language", "fr"),
    ]


def test_instagram_switch_keeps_the_screen_instagram_shows(monkeypatch):
    from taktik.core.social_media.instagram.workflows.management import agent_handler

    bridge_calls, cli_calls = [], []
    _bridge_uses(monkeypatch, agent_handler.run_instagram_account, _instagram_factories(bridge_calls))
    exit_code = _instagram_bridge({"workflowType": "switch_account", "targetUsername": " bob "},
                                  FakeApp(bridge_calls, running=True))._run_switch(DEVICE)
    _instagram_cli("instagram.account.switch_account", {"targetUsername": " bob "},
                   FakeApp(cli_calls, running=True), _instagram_factories(cli_calls))

    assert exit_code == 0
    assert bridge_calls == cli_calls == [
        ("is_running",), ("built", "switch", True, DEVICE_ID), ("switch_account", "bob"),
    ]


def test_instagram_account_list_restarts_an_instagram_that_is_not_open(monkeypatch):
    from taktik.core.social_media.instagram.workflows.management import agent_handler

    calls = []
    _bridge_uses(monkeypatch, agent_handler.run_instagram_account, _instagram_factories(calls))
    _instagram_bridge({"workflowType": "list_accounts"}, FakeApp(calls, running=False))._run_list_accounts(DEVICE)

    assert calls == [("is_running",), ("restart",), ("built", "switch", True, DEVICE_ID), ("list_accounts",)]


def test_instagram_bridge_refuses_a_payload_before_touching_the_phone(monkeypatch):
    from bridges.instagram.account.runtime import launch
    from taktik.core.social_media.instagram.workflows.management import agent_handler

    calls, errors = [], []
    _bridge_uses(monkeypatch, agent_handler.run_instagram_account, _instagram_factories(calls))
    monkeypatch.setattr(launch, "send_error", errors.append)
    exit_code = _instagram_bridge({"workflowType": "login", "username": "alice"}, FakeApp(calls))._run_login(DEVICE)

    assert exit_code == 1
    assert calls == []
    assert errors == ["Instagram login requires password"]


def test_cli_auth_login_runs_the_account_launcher(monkeypatch):
    from taktik.cli.commands import management_cmds
    from taktik.cli.common.instagram_host import CliInstagramHost
    from taktik.core.social_media.instagram.workflows.management import agent_handler

    calls = []

    class _Manager:
        device = DEVICE

        @staticmethod
        def list_devices():
            return [{"id": DEVICE_ID, "status": "device"}]

        def connect(self, device_id=None):
            return True

    class _Instagram:
        def __init__(self, *_a, **_k):
            pass

        def is_installed(self):
            return True

        def launch(self):
            calls.append(("warm_launch",))
            return True

    monkeypatch.setattr(management_cmds, "DeviceManager", _Manager)
    monkeypatch.setattr(management_cmds, "InstagramManager", _Instagram)
    monkeypatch.setattr(CliInstagramHost, "account_app", lambda self, _package: FakeApp(calls))
    _bridge_uses(monkeypatch, agent_handler.register_instagram_account_handlers, _instagram_factories(calls))

    result = CliRunner().invoke(management_cmds.management,
                                ["auth", "login", "-d", DEVICE_ID, "-u", "alice", "-p", "pw"])

    assert result.exit_code == 0, result.output
    assert calls[0] == ("restart",)
    assert calls[1] == ("built", "login", True, DEVICE_ID)
    assert dict(calls[2][1])["username"] == "alice"


# --------------------------------------------------------------------------- TikTok


def _tiktok_factories(calls):
    def build(name):
        class Fake:
            def __init__(self, device, device_id, notifier=None):
                calls.append(("built", name, device is DEVICE, device_id))

            def execute(self, **params):
                calls.append((name, tuple(sorted(params.items()))))
                return {"success": True, "message": "ok", "error_type": None}

            def run(self, target):
                calls.append((name, target))
                return {"success": True, "language_before": "en", "language_after": target}

        return Fake

    return {
        "login_workflow_factory": build("login"),
        "logout_workflow_factory": build("logout"),
        "signup_workflow_factory": build("register"),
        "change_language_workflow_factory": build("change_language"),
    }


def _tiktok_bridge(config, app):
    from bridges.tiktok.account.runtime.bridge import TikTokAccountBridge

    bridge = TikTokAccountBridge.__new__(TikTokAccountBridge)  # no signal handlers in a test process
    bridge.config = {"deviceId": DEVICE_ID, **config}
    bridge.device_id = DEVICE_ID
    bridge.workflow_type = config["workflowType"]
    bridge.package_name = None
    bridge._app = app
    return bridge


def _tiktok_cli(workflow_id, params, app, factories):
    from taktik.core.social_media.tiktok.workflows.management.agent_handler import (
        register_tiktok_account_handlers,
    )

    registry = WorkflowRegistry()
    register_tiktok_account_handlers(registry, device=DEVICE, device_id=DEVICE_ID,
                                     tiktok_account_app=lambda _package: app, **factories)
    invocation = WorkflowInvocation(platform="tiktok", workflow_id=workflow_id, params=params)
    return registry.resolve(workflow_id)(invocation, {"deviceId": DEVICE_ID})


def _tiktok_app(calls):
    return FakeApp(calls, package="com.zhiliaoapp.musically")


def test_every_tiktok_account_flow_of_the_bridge_is_launched():
    from taktik.core.social_media.tiktok.workflows.management.agent_handler import (
        register_tiktok_account_handlers,
    )

    registry = WorkflowRegistry()
    register_tiktok_account_handlers(registry, device=DEVICE, device_id=DEVICE_ID)
    for workflow_type in TIKTOK_BRIDGE_TYPES:
        assert registry.resolve(f"tiktok.account.{workflow_type}")


@pytest.mark.parametrize("workflow_type, runner, page", [
    ("login", "_run_login", {"username": "alice", "password": "pw", "saveSession": False}),
    ("register", "_run_register", {"method": "email", "email": "a@example.com", "nickname": "Al",
                                   "gmailPassword": "g", "tiktokPassword": "t"}),
    ("logout", "_run_logout", {}),
    ("change_language", "_run_change_language", {"targetLanguage": "fr"}),
])
def test_tiktok_account_flow_is_the_same_call_from_the_bridge_and_the_cli(monkeypatch, workflow_type, runner, page):
    from taktik.core.social_media.tiktok.workflows.management import agent_handler

    bridge_calls, cli_calls = [], []
    _bridge_uses(monkeypatch, agent_handler.run_tiktok_account, _tiktok_factories(bridge_calls))
    exit_code = getattr(_tiktok_bridge({"workflowType": workflow_type, **page}, _tiktok_app(bridge_calls)), runner)(DEVICE)
    _tiktok_cli(f"tiktok.account.{workflow_type}", page, _tiktok_app(cli_calls), _tiktok_factories(cli_calls))

    assert exit_code == 0
    assert bridge_calls == cli_calls
    assert bridge_calls[:2] == [("restart",), ("built", workflow_type, True, DEVICE_ID)]


def test_tiktok_language_change_without_a_language_is_refused_before_the_restart(monkeypatch):
    from taktik.core.social_media.tiktok.workflows.management import agent_handler

    calls = []
    _bridge_uses(monkeypatch, agent_handler.run_tiktok_account, _tiktok_factories(calls))
    exit_code = _tiktok_bridge({"workflowType": "change_language"}, _tiktok_app(calls))._run_change_language(DEVICE)

    assert exit_code == 1
    assert calls == []
