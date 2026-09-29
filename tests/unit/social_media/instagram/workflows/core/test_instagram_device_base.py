"""The Instagram device a run drives: the clone-aware proxy mounted on every connection (the stock
app included), the facade over the proxy, the selector overrides of the installed version, the
package a clone registers, `rid` and the historical `restart_instagram`.

Pinned on doubles of the connection and the app (no device, no adb); the proxy, the facade and the
override registry are the real ones, their global state patched.
"""

from types import SimpleNamespace

import pytest

import taktik.core.clone as clone
from bridges.instagram.common.bridge import InstagramBridgeBase
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.compat.selectors import setup as compat_setup
from taktik.core.shared.device import app_manager, connection
from taktik.core.shared.device.facade import BaseDeviceFacade

STOCK = "com.instagram.android"
CLONE = "com.taktik.ig1"


class _Raw:
    """A uiautomator2 device (no `.device` attribute of its own)."""


class _Connection:
    """The connection service: a manager and a raw device once connected."""

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
        return (1080, 2400)

    def connect(self):
        self.device_manager = SimpleNamespace(device=None)
        self._device = _Connection.next_device
        return True


class _App:
    """`AppService`, recorded; `version` is what the phone says is installed."""

    built = []
    version = None

    def __init__(self, connection, platform, package_override=None):
        self.platform, self.package_override = platform, package_override
        self.calls = []
        _App.built.append(self)

    def restart(self):
        self.calls.append("restart")
        return True

    def get_installed_version(self):
        self.calls.append("version")
        return _App.version


@pytest.fixture
def phone(monkeypatch):
    """The doubles, and what the base does to the process-wide registries."""
    _Connection.built, _Connection.next_device = [], _Raw()
    _App.built, _App.version = [], None
    monkeypatch.setattr(connection, "ConnectionService", _Connection)
    monkeypatch.setattr(app_manager, "AppService", _App)
    seen = SimpleNamespace(active_packages=[], overrides=[])
    monkeypatch.setattr(clone, "set_active_package", seen.active_packages.append)
    monkeypatch.setattr(compat_setup, "apply_version_overrides",
                        lambda platform, version: seen.overrides.append((platform, version)) or 0)
    return seen


def test_the_platform_and_its_package():
    assert (InstagramBridgeBase.PLATFORM, InstagramBridgeBase.DEFAULT_PACKAGE) == ("instagram", STOCK)


def test_the_stock_app_gets_the_proxy_too_and_registers_no_clone(phone):
    base = InstagramBridgeBase("SERIAL")

    assert base.connect() is True

    proxy = base._connection._device
    assert isinstance(proxy, CloneAwareDeviceProxy) and proxy.clone_package == STOCK
    assert proxy.raw is _Connection.next_device
    assert base.device_manager.device is proxy
    assert isinstance(base.device, BaseDeviceFacade) and base.device.device is proxy
    assert phone.active_packages == []
    assert _App.built[0].package_override is None


def test_a_clone_registers_its_package_and_is_the_one_driven(phone):
    base = InstagramBridgeBase("SERIAL", package_name=CLONE)

    base.connect()

    assert phone.active_packages == [CLONE]
    assert base._connection._device.clone_package == CLONE
    assert _App.built[0].package_override == CLONE


def test_a_device_already_proxied_is_kept(phone):
    already = CloneAwareDeviceProxy(_Raw(), CLONE)
    _Connection.next_device = already
    base = InstagramBridgeBase("SERIAL", package_name=CLONE)

    base.connect()

    assert base._connection._device is already
    assert base.device.device is already


class _ReadOnlyConnection:
    """A connection whose device the base cannot replace."""

    def __init__(self, device_id):
        self.device_id = device_id
        self.device_manager = None
        self._held = None

    @property
    def _device(self):
        return self._held

    @property
    def device(self):
        return self._held

    @property
    def screen_size(self):
        return (1080, 2400)

    def connect(self):
        self.device_manager = SimpleNamespace(device=None)
        self._held = _Raw()
        return True


def test_a_connection_that_keeps_its_own_device_still_connects(phone, monkeypatch):
    monkeypatch.setattr(connection, "ConnectionService", _ReadOnlyConnection)
    base = InstagramBridgeBase("SERIAL")

    assert base.connect() is True
    assert isinstance(base._connection._device, _Raw)
    assert isinstance(base.device.device, CloneAwareDeviceProxy)
    assert base.device_manager.device is base.device.device


def test_the_overrides_of_the_installed_version_are_applied_on_the_facade(phone, monkeypatch):
    _App.version = "442.0.0.1"
    base = InstagramBridgeBase("SERIAL")
    facade_ready = []
    monkeypatch.setattr(compat_setup, "apply_version_overrides",
                        lambda platform, version: facade_ready.append(isinstance(base.device, BaseDeviceFacade))
                        or phone.overrides.append((platform, version)))

    base.connect()

    assert phone.overrides == [("instagram", "442.0.0.1")]
    assert facade_ready == [True]


def test_no_installed_version_no_overrides(phone):
    InstagramBridgeBase("SERIAL").connect()

    assert phone.overrides == []
    assert _App.built[0].calls == ["version"]


def test_overrides_that_fail_never_stop_the_connection(phone, monkeypatch):
    _App.version = "442.0.0.1"

    def broken(platform, version):
        raise KeyError("no such override file")

    monkeypatch.setattr(compat_setup, "apply_version_overrides", broken)

    assert InstagramBridgeBase("SERIAL").connect() is True


def test_rid_names_the_resource_of_the_driven_package():
    assert InstagramBridgeBase("SERIAL").rid(f"{STOCK}:id/search_tab") == f"{STOCK}:id/search_tab"
    assert InstagramBridgeBase("SERIAL", package_name=CLONE).rid(f"{STOCK}:id/search_tab") == f"{CLONE}:id/search_tab"


def test_restart_instagram_restarts_the_app(phone):
    base = InstagramBridgeBase("SERIAL")
    base.connect()

    base.restart_instagram()

    assert base._app.calls == ["version", "restart"]
