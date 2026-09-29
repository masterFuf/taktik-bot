"""The connection to a phone: its screen size, the health of its uiautomator2 agent (ATX), the
connection service that owns the one `DeviceManager` of a run, and the phone a host already
connected (the CLI, the Lab session), seen as such a connection.

What each one answers is pinned here, on doubles of the phone (no device, no adb).
"""

from types import SimpleNamespace

import pytest

from taktik.core.shared.device import atx_health, connected_device, connection, screen


# ------------------------------------------------------------------------------------ screen size

class _Device:
    def __init__(self, info):
        self._info = info

    @property
    def info(self):
        if isinstance(self._info, Exception):
            raise self._info
        return self._info


def test_the_size_is_read_from_the_device_info():
    assert screen.read_screen_size(_Device({"displayWidth": 720, "displayHeight": 1600})) == (720, 1600)


def test_a_missing_dimension_takes_the_default_of_that_axis():
    assert screen.read_screen_size(_Device({"displayWidth": 720})) == (720, 2340)
    assert screen.read_screen_size(_Device({}), default=(1, 2)) == (1, 2)


def test_an_unreadable_device_answers_the_default():
    assert screen.read_screen_size(_Device(RuntimeError("server gone"))) == screen.DEFAULT_SCREEN_SIZE
    assert screen.DEFAULT_SCREEN_SIZE == (1080, 2340)


# ---------------------------------------------------------------------------------- ATX health

class _Agent:
    """A device manager whose agent answers `status`, and repairs itself when `repairs`."""

    def __init__(self, status, repairs=False):
        self.status = status
        self.repairs = repairs
        self.repair_calls = []

    def get_atx_status(self):
        if isinstance(self.status, Exception):
            raise self.status
        return self.status

    def _verify_and_repair_atx(self, max_retries):
        self.repair_calls.append(max_retries)
        return self.repairs


def test_no_manager_is_not_connected():
    assert atx_health.check_atx_health(None) == {"atx_healthy": False, "error": "Not connected", "repaired": False}


def test_a_healthy_agent_is_left_alone():
    agent = _Agent({"atx_healthy": True})

    assert atx_health.check_atx_health(agent) == {"atx_healthy": True, "error": None, "repaired": False}
    assert agent.repair_calls == []


def test_an_unhealthy_agent_is_repaired():
    agent = _Agent({"atx_healthy": False, "error": "agent down"}, repairs=True)

    assert atx_health.check_atx_health(agent, max_retries=5) == {"atx_healthy": True, "error": None, "repaired": True}
    assert agent.repair_calls == [5]


def test_a_failed_repair_says_why_the_agent_was_unhealthy():
    agent = _Agent({"atx_healthy": False, "error": "agent down"})

    assert atx_health.check_atx_health(agent) == {"atx_healthy": False, "error": "agent down", "repaired": False}
    assert agent.repair_calls == [3]


def test_without_repair_the_agent_is_only_checked():
    agent = _Agent({"atx_healthy": False})

    assert atx_health.check_atx_health(agent, repair=False) == {
        "atx_healthy": False, "error": "Unknown ATX error", "repaired": False}
    assert agent.repair_calls == []


def test_an_unreadable_agent_is_an_unhealthy_one():
    assert atx_health.check_atx_health(_Agent(OSError("adb gone"))) == {
        "atx_healthy": False, "error": "adb gone", "repaired": False}


# -------------------------------------------------------------------------- the connection service

class _DeviceManager:
    """`DeviceManager`, recorded: `connects` says whether `connect()` succeeds, `device` what it holds."""

    built = []

    def __init__(self, device_id=None):
        self.device_id = device_id
        self.device = None
        self.disconnected = False
        _DeviceManager.built.append(self)

    def connect(self):
        self.device = self.next_device
        return self.connects

    def disconnect(self):
        self.disconnected = True


@pytest.fixture
def managers(monkeypatch):
    _DeviceManager.built = []
    _DeviceManager.connects = True
    _DeviceManager.next_device = _Device({"displayWidth": 720, "displayHeight": 1600})
    monkeypatch.setattr(connection, "DeviceManager", _DeviceManager)
    return _DeviceManager


def test_before_connect_nothing_is_held():
    service = connection.ConnectionService("SERIAL")

    assert (service.device, service.device_manager, service.is_connected) == (None, None, False)
    assert service.screen_size == (1080, 2340)


def test_connect_holds_one_manager_its_device_and_the_screen(managers):
    service = connection.ConnectionService("SERIAL")

    assert service.connect() is True
    assert [m.device_id for m in managers.built] == ["SERIAL"]
    assert service.device_manager is managers.built[0]
    assert service.device is managers.next_device
    assert (service.screen_size, service.screen_width, service.screen_height) == ((720, 1600), 720, 1600)
    assert service.is_connected is True


def test_a_second_connect_keeps_the_connection(managers):
    service = connection.ConnectionService("SERIAL")
    service.connect()

    assert service.connect() is True
    assert len(managers.built) == 1


def test_a_refused_connection_holds_nothing_usable(managers):
    managers.connects = False
    service = connection.ConnectionService("SERIAL")

    assert service.connect() is False
    assert service.is_connected is False


def test_a_manager_without_device_is_no_connection(managers):
    managers.next_device = None
    service = connection.ConnectionService("SERIAL")

    assert service.connect() is False
    assert service.is_connected is False


def test_a_manager_that_cannot_be_built_is_no_connection(monkeypatch):
    def refuse(device_id=None):
        raise RuntimeError("uiautomator2 missing")

    monkeypatch.setattr(connection, "DeviceManager", refuse)

    assert connection.ConnectionService("SERIAL").connect() is False


def test_disconnect_lets_the_device_go_and_keeps_the_manager(managers):
    service = connection.ConnectionService("SERIAL")
    service.connect()
    manager = service.device_manager

    service.disconnect()

    assert manager.disconnected is True
    assert (service.device, service.is_connected) == (None, False)
    assert service.device_manager is manager


def test_a_manager_that_fails_to_disconnect_still_ends_the_connection(managers):
    service = connection.ConnectionService("SERIAL")
    service.connect()

    def broken():
        raise OSError("adb gone")

    service.device_manager.disconnect = broken
    service.disconnect()

    assert service.is_connected is False


def test_the_atx_check_runs_on_the_manager_of_the_connection(monkeypatch, managers):
    asked = []
    monkeypatch.setattr(connection, "perform_atx_health_check",
                        lambda manager, repair, max_retries: asked.append((manager, repair, max_retries)) or "verdict")
    service = connection.ConnectionService("SERIAL")
    service.connect()

    assert service.check_atx_health(repair=False, max_retries=7) == "verdict"
    assert asked == [(service.device_manager, False, 7)]


# ------------------------------------------------------------- the phone a host already connected

def test_a_connected_phone_is_seen_as_a_connection():
    device = _Device({"displayWidth": 720, "displayHeight": 1600})
    manager = SimpleNamespace(device=device)

    phone = connected_device.ConnectedDevice(manager, "SERIAL")

    assert (phone.device_manager, phone.device_id, phone.device) == (manager, "SERIAL", device)
    assert phone.screen_size == (720, 1600)
    assert phone.connect() is True


def test_the_device_is_the_one_held_when_the_phone_was_handed():
    manager = SimpleNamespace(device="FIRST")
    phone = connected_device.ConnectedDevice(manager, "SERIAL")
    manager.device = "SECOND"

    assert phone.device == "FIRST"


def test_a_host_without_device_hands_no_connection():
    phone = connected_device.ConnectedDevice(SimpleNamespace(), "SERIAL")

    assert phone.device is None
    assert phone.connect() is False


class _Base:
    """A base that connects through whatever `_connection` it holds."""

    def __init__(self):
        self._connection = "its own connection"

    def connect(self):
        return self._connection.connect()


def test_a_base_is_connected_on_the_phone_of_its_host():
    manager = SimpleNamespace(device="DEVICE")
    base = _Base()

    assert connected_device.on_connected_device(base, manager, "SERIAL") is base
    assert isinstance(base._connection, connected_device.ConnectedDevice)
    assert (base._connection.device_manager, base._connection.device_id) == (manager, "SERIAL")


def test_a_host_without_device_cannot_connect_a_base():
    with pytest.raises(RuntimeError, match="No connected device for SERIAL"):
        connected_device.on_connected_device(_Base(), SimpleNamespace(), "SERIAL")
