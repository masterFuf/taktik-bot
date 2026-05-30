from unittest.mock import Mock

from taktik.core.device import device as device_module


def test_get_connected_devices_filters_non_ready_entries(monkeypatch):
    class FakeSharedDeviceManager:
        @staticmethod
        def list_devices():
            return [
                {"id": "serial-ready", "status": "device"},
                {"id": "serial-offline", "status": "offline"},
                {"id": "serial-unauthorized", "status": "unauthorized"},
            ]

    monkeypatch.setattr(device_module, "SharedDeviceManager", FakeSharedDeviceManager)

    assert device_module.DeviceManager.get_connected_devices() == ["serial-ready"]


def test_connect_to_device_delegates_to_shared_manager(monkeypatch):
    calls = {}
    fake_device = object()

    class FakeSharedDeviceManager:
        def __init__(self, device_id=None):
            calls["device_id"] = device_id
            self.device = fake_device

        def connect(self, verify_atx=True):
            calls["verify_atx"] = verify_atx
            return True

    monkeypatch.setattr(device_module, "SharedDeviceManager", FakeSharedDeviceManager)

    device = device_module.DeviceManager.connect_to_device("emulator-5554")

    assert device is fake_device
    assert calls == {"device_id": "emulator-5554", "verify_atx": False}


def test_launch_app_preserves_legacy_raw_device_contract():
    device = Mock()

    assert device_module.DeviceManager.launch_app(device, "com.instagram.android") is True

    device.app_start.assert_called_once_with("com.instagram.android")


def test_stop_app_preserves_legacy_raw_device_contract():
    device = Mock()

    assert device_module.DeviceManager.stop_app(device, "com.instagram.android") is True

    device.app_stop.assert_called_once_with("com.instagram.android")
