"""The Lab runs a whole notifications run through the launcher the desktop bridge calls.

`notifications.run` hands `run_instagram_notifications` (the one launcher of
`instagram.engagement.notifications`, called by `notifications_bridge` and by the CLI) the Lab
session's device instead of a second connection, and the Lab's clean restart. The run's events
come back in the result, never on stdout (the session's own JSON lines).
"""

import inspect
from types import SimpleNamespace

import pytest

from bridges.compat.diagnostics.actions.instagram import ACTION_REGISTRY, register_actions
from bridges.compat.diagnostics.actions.instagram import app as lab_app
from bridges.instagram.engagement.runtime.notifications import commands as bridge_commands
from taktik.core.social_media.instagram.workflows.management.notifications import agent_handler

SERIAL = "lab-device"


@pytest.fixture(autouse=True)
def _registered():
    register_actions()


class _UntouchableDevice:
    """A device the test forbids to touch: a refused command must never reach the phone."""

    def __getattr__(self, name):
        raise AssertionError(f"the device was touched ({name})")


class _Manager:
    """The Lab's app lifecycle, recorded."""

    calls = []

    def __init__(self, device_id):
        self.device_id = device_id
        self.device = None

    def launch_app(self, package, stop_first=False):
        self.calls.append(("launch", self.device_id, package, stop_first))
        return True

    def stop_app(self, package):
        self.calls.append(("stop", self.device_id, package))
        return True


@pytest.fixture
def lab_lifecycle(monkeypatch):
    _Manager.calls = []
    monkeypatch.setattr(lab_app, "DeviceManager", _Manager)
    monkeypatch.setattr(lab_app, "get_active_package", lambda: "com.instagram.android")
    return _Manager.calls


def _bundle(device=None, device_id=SERIAL):
    device = device if device is not None else SimpleNamespace(app_current=lambda: {"package": "com.instagram.android"})
    return SimpleNamespace(device=device, device_id=device_id)


def test_the_bridge_and_the_lab_share_one_launcher():
    assert bridge_commands.run_instagram_notifications is agent_handler.run_instagram_notifications
    assert "notifications.run" in ACTION_REGISTRY


def test_the_lab_run_goes_through_the_launcher_with_the_lab_params(monkeypatch, lab_lifecycle):
    seen = {}

    def launcher(config, *, connect, emit=None, instagram_ai_service=None):
        seen.update(config=dict(config), ai=instagram_ai_service)
        return {"type": "result", "command": "scan", "success": True, "count": 4, "message": "4 notifications"}

    monkeypatch.setattr(agent_handler, "run_instagram_notifications", launcher)
    result = ACTION_REGISTRY["notifications.run"](_bundle(), {"scroll": 2, "followSuggestions": 1})

    # The launcher's own keys; the command defaults to a scan, as the CLI handler does.
    assert seen["config"] == {"command": "scan", "scroll": 2, "followSuggestions": 1}
    # The app never sends an `ai` block, and the bridge's AI service prints on stdout.
    assert seen["ai"] is None
    assert result["success"] is True
    assert "4 notifications" in result["message"]
    assert result["details"]["result"]["count"] == 4


def test_the_lab_connect_takes_what_the_launcher_passes(monkeypatch, lab_lifecycle):
    # The launcher calls `connect` with the arguments of its declared `Connect` type.
    seen = {}

    def launcher(config, *, connect, emit=None, instagram_ai_service=None):
        seen["connect"] = connect
        return {"type": "result", "command": "scan", "success": True, "message": ""}

    monkeypatch.setattr(agent_handler, "run_instagram_notifications", launcher)
    ACTION_REGISTRY["notifications.run"](_bundle(), {})

    declared = len(agent_handler.Connect.__args__) - 1
    assert len(inspect.signature(seen["connect"]).parameters) == declared


def test_the_runtime_is_the_session_device_and_the_lab_restart(monkeypatch, lab_lifecycle):
    runtimes = []

    def launcher(config, *, connect, emit=None, instagram_ai_service=None):
        runtimes.append(connect(None, True))
        runtimes.append(connect(None, False))
        runtimes[0].stop()
        return {"type": "result", "command": "scan", "success": True, "message": ""}

    monkeypatch.setattr(agent_handler, "run_instagram_notifications", launcher)
    bundle = _bundle()
    ACTION_REGISTRY["notifications.run"](bundle, {})

    restarted, current = runtimes
    assert restarted.device is bundle.device and restarted.device_id == SERIAL
    assert current.device is bundle.device
    # A scan restarts Instagram cleanly (force-stop then start), a row verb does not; the run's
    # end closes it. All on the session's phone.
    assert lab_lifecycle == [
        ("launch", SERIAL, "com.instagram.android", True),
        ("stop", SERIAL, "com.instagram.android"),
    ]
    restarted.restart_instagram()
    assert lab_lifecycle[-1] == ("launch", SERIAL, "com.instagram.android", True)


def test_the_run_events_come_back_in_the_result_not_on_stdout(monkeypatch, capsys, lab_lifecycle):
    def launcher(config, *, connect, emit=None, instagram_ai_service=None):
        emit({"type": "notification_step", "step": "scan", "step_status": "running", "message": "Reading"})
        emit({"type": "active_account", "username": "someone"})
        return {"type": "result", "command": "scan", "success": False, "message": "nothing read"}

    monkeypatch.setattr(agent_handler, "run_instagram_notifications", launcher)
    result = ACTION_REGISTRY["notifications.run"](_bundle(), {})

    assert result["success"] is False
    assert [event["type"] for event in result["details"]["events"]] == ["notification_step", "active_account"]
    assert capsys.readouterr().out == ""


def test_a_refused_command_is_the_launcher_refusal_before_the_phone(lab_lifecycle):
    result = ACTION_REGISTRY["notifications.run"](_bundle(device=_UntouchableDevice()), {"command": "reply"})

    assert result["success"] is False
    assert "username is required for reply" in result["message"]
    assert lab_lifecycle == []


def test_no_serial_no_run(monkeypatch, lab_lifecycle):
    called = []
    monkeypatch.setattr(agent_handler, "run_instagram_notifications", lambda *a, **k: called.append(1))
    result = ACTION_REGISTRY["notifications.run"](_bundle(device=SimpleNamespace(), device_id=None), {})

    assert result["success"] is False
    assert called == []
