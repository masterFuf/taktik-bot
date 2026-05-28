from taktik.core.social_media.tiktok.ui.detectors import keyboard


class FakeXpathResult:
    def __init__(self, device):
        self.device = device

    def wait(self, timeout: float = 0.0) -> bool:
        return self.device.visible


class FakeKeyboardDevice:
    def __init__(self, visible: bool = True, press_raises: bool = False):
        self.visible = visible
        self.press_raises = press_raises
        self.press_calls = 0

    def xpath(self, _selector: str):
        return FakeXpathResult(self)

    def press(self, key: str) -> None:
        self.press_calls += 1
        if self.press_raises:
            raise RuntimeError("press failed")
        assert key == "back"
        self.visible = False


def test_dismiss_keyboard_uses_device_back_when_keyboard_is_visible():
    device = FakeKeyboardDevice(visible=True)

    assert keyboard.dismiss_keyboard(device, device_id="device-1", settle_delay=0)
    assert device.press_calls == 1
    assert not device.visible


def test_dismiss_keyboard_noops_when_keyboard_is_already_hidden():
    device = FakeKeyboardDevice(visible=False)

    assert keyboard.dismiss_keyboard(device, device_id="device-1", settle_delay=0)
    assert device.press_calls == 0


def test_dismiss_keyboard_falls_back_to_adb_keyevent(monkeypatch):
    device = FakeKeyboardDevice(visible=True, press_raises=True)
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        device.visible = False

    monkeypatch.setattr(keyboard.subprocess, "run", fake_run)

    assert keyboard.dismiss_keyboard(device, device_id="device-1", settle_delay=0)
    assert calls == [["adb", "-s", "device-1", "shell", "input", "keyevent", "4"]]
