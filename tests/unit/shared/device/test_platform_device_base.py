"""The base of a platform's app on a connected phone: one connection, the app lifecycle
(`AppService`), the device facade over what the platform mounted; the order of `connect()`, and
the restart and stop of a run.

Pinned on doubles of the connection and the app (no device, no adb). The facade itself is pinned by
`tests/unit/bridges/test_bridge_exposes_device_facade.py`.
"""

import pytest

from taktik.core.shared.device.platform_device import PlatformDeviceBase
from taktik.core.compat.selectors import setup as compat_setup
from taktik.core.shared.device import app_manager, connection
from taktik.core.shared.device.facade import BaseDeviceFacade


class _Raw:
    """A uiautomator2 device (no `.device` attribute of its own)."""


class _Connection:
    """The connection service, recorded: `connects` says whether `connect()` succeeds."""

    connects = True
    built = []

    def __init__(self, device_id):
        self.device_id = device_id
        self.device_manager = None
        self._device = None
        _Connection.built.append(self)

    @property
    def device(self):
        return self._device

    @property
    def screen_size(self):
        return (720, 1600)

    def connect(self):
        if not self.connects:
            return False
        self.device_manager = "MANAGER"
        self._device = _Raw()
        return True


class _App:
    """`AppService`, recorded."""

    built = []

    def __init__(self, connection, platform, package_override=None):
        self.connection, self.platform, self.package_override = connection, platform, package_override
        self.calls = []
        self.stopped = True
        _App.built.append(self)

    def restart(self):
        self.calls.append("restart")
        return True

    def stop(self):
        self.calls.append("stop")
        if isinstance(self.stopped, Exception):
            raise self.stopped
        return self.stopped

    def get_installed_version(self):
        raise AssertionError("a platform without selector overrides reads no version")


@pytest.fixture(autouse=True)
def doubles(monkeypatch):
    _Connection.built, _Connection.connects, _App.built = [], True, []
    monkeypatch.setattr(connection, "ConnectionService", _Connection)
    monkeypatch.setattr(app_manager, "AppService", _App)
    monkeypatch.setattr(compat_setup, "apply_version_overrides",
                        lambda platform, version: pytest.fail("no selector overrides for this platform"))


class _Platform(PlatformDeviceBase):
    PLATFORM = "threads"
    DEFAULT_PACKAGE = "com.instagram.barcelona"


def test_a_new_base_holds_its_connection_and_nothing_else():
    base = _Platform("SERIAL")

    assert [c.device_id for c in _Connection.built] == ["SERIAL"]
    assert base._connection is _Connection.built[0]
    assert (base.device_id, base.package_name) == ("SERIAL", "com.instagram.barcelona")
    assert (base.device, base.device_manager, base._app) == (None, None, None)
    assert (base.screen_width, base.screen_height) == (1080, 2340)


def test_a_named_package_is_the_package_of_the_base():
    assert _Platform("SERIAL", package_name="com.other.threads").package_name == "com.other.threads"


def test_a_refused_connection_builds_no_app():
    _Connection.connects = False
    base = _Platform("SERIAL")

    assert base.connect() is False
    assert (base._app, base.device) == (None, None)
    assert _App.built == []


def test_connect_holds_the_manager_the_screen_and_the_app():
    base = _Platform("SERIAL")

    assert base.connect() is True
    assert base.device_manager == "MANAGER"
    assert (base.screen_width, base.screen_height) == (720, 1600)
    assert [(a.connection, a.platform, a.package_override) for a in _App.built] == [
        (base._connection, "threads", None)]
    assert base._app is _App.built[0]


def test_a_package_other_than_the_default_overrides_the_app_package():
    _Platform("SERIAL", package_name="com.other.threads").connect()

    assert _App.built[0].package_override == "com.other.threads"


def test_the_facade_wraps_what_the_platform_mounted_after_the_connection():
    mounted = object()

    class _Mounting(_Platform):
        def _after_connect(self):
            self.device = mounted

    base = _Mounting("SERIAL")
    base.connect()

    assert isinstance(base.device, BaseDeviceFacade)
    assert base.device.device is mounted


def test_restart_before_connect_is_an_error():
    with pytest.raises(RuntimeError, match=r"_Platform.restart\(\) called before connect\(\)"):
        _Platform("SERIAL").restart()


def test_restart_restarts_the_app():
    base = _Platform("SERIAL")
    base.connect()

    base.restart()

    assert base._app.calls == ["restart"]


def test_stop_before_connect_stops_nothing():
    assert _Platform("SERIAL").stop() is False


@pytest.mark.parametrize("stopped, verdict", [(True, True), (False, False), ("yes", True),
                                              (OSError("adb gone"), False)])
def test_stop_is_the_verdict_of_the_app_and_never_raises(stopped, verdict):
    base = _Platform("SERIAL")
    base.connect()
    base._app.stopped = stopped

    assert base.stop() is verdict
    assert base._app.calls == ["stop"]
