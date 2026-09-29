"""The Lab runs a whole notifications run through the launcher the desktop bridge calls.

`notifications.run` hands `run_instagram_notifications` (the one launcher of
`instagram.engagement.notifications`, called by `notifications_bridge` and by the CLI) the device
the bridge connects, `InstagramDeviceBase`, on the Lab session's device instead of a second
connection (decision D5 of 2026-09-27): the same clone-aware device, the same clean restart through
`AppService`, by the helper the CLI uses (`taktik/core/shared/device/connected_device.py`). The run's
events come back in the result, never on stdout (the session's own JSON lines).
"""

import inspect
from types import SimpleNamespace

import pytest

from bridges.tools.lab.actions.instagram import ACTION_REGISTRY, register_actions
from bridges.tools.lab.actions.instagram import app as lab_app
from bridges.instagram.notifications import commands as bridge_commands
from taktik.core.social_media.instagram.workflows.common.device import InstagramDeviceBase
from taktik.core.social_media.instagram.workflows.notifications import agent_handler

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


class _AppService:
    """The bridges' app lifecycle, as the real one uses its connection: it restarts and stops the app
    through the connection's device manager (`stop_app`, `launch_app`), and says which service did."""

    calls = []

    def __init__(self, connection, platform="instagram", package_override=None):
        self._conn = connection
        self.package = package_override or "com.instagram.android"

    def get_installed_version(self):
        return None

    def restart(self):
        self.calls.append("restart")
        self._conn.device_manager.stop_app(self.package)
        return self._conn.device_manager.launch_app(self.package)

    def stop(self):
        self.calls.append("stop")
        return self._conn.device_manager.stop_app(self.package)


@pytest.fixture
def bridge_lifecycle(monkeypatch):
    import taktik.core.shared.device.app_manager as app_manager

    _AppService.calls = []
    monkeypatch.setattr(app_manager, "AppService", _AppService)
    return _AppService.calls


class _RawDevice:
    serial = SERIAL


def test_the_runtime_is_the_bridge_class_on_the_session_device(monkeypatch, lab_lifecycle, bridge_lifecycle):
    import taktik.core.clone as clone

    # A clone's bridge registers its package for the whole process: put it back after the test.
    monkeypatch.setattr(clone, "_active_package", clone.get_active_package())
    runtimes = []

    def launcher(config, *, connect, emit=None, instagram_ai_service=None):
        runtimes.append(connect(None, True))
        runtimes.append(connect("com.instagram.clone", False))
        runtimes[0].stop()
        return {"type": "result", "command": "scan", "success": True, "message": ""}

    monkeypatch.setattr(agent_handler, "run_instagram_notifications", launcher)
    raw = _RawDevice()
    bundle = _bundle(device=SimpleNamespace(_device=raw))
    ACTION_REGISTRY["notifications.run"](bundle, {})

    restarted, clone = runtimes
    # The class the desktop bridge connects, on the phone the session holds: no second connection.
    assert isinstance(restarted, InstagramDeviceBase) and restarted.device_id == SERIAL
    assert restarted._connection.device._device is raw
    assert clone.package_name == "com.instagram.clone"
    # A scan restarts Instagram through the bridges' AppService, a row verb does not; the run's
    # end closes it. The service drives the session's phone (its serial), never a new connection.
    assert bridge_lifecycle == ["restart", "stop"]
    assert lab_lifecycle == [
        ("stop", SERIAL, "com.instagram.android"),
        ("launch", SERIAL, "com.instagram.android", False),
        ("stop", SERIAL, "com.instagram.android"),
    ]


def test_the_lab_and_the_cli_connect_a_bridge_by_one_helper(monkeypatch):
    from taktik.core.shared.device import connected_device
    from taktik.cli.hosts import instagram as instagram_host

    connected = []
    monkeypatch.setattr(connected_device, "on_connected_device",
                        lambda base, device_manager, device_id: connected.append(type(base).__name__) or base)
    host = instagram_host.CliInstagramHost(SimpleNamespace(device=object()), SERIAL)
    host.notifications_runtime(None, restart=False)

    assert connected == ["InstagramDeviceBase"]
    assert not hasattr(instagram_host, "_on_connected_device")


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
