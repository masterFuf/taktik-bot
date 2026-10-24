"""The screen size is read, never made up: when uiautomator2 cannot give it, `wm size` by adb does.

Pixel 6 Pro, Android 17, 2026-10-24: the uiautomator2 server answers `deviceInfo` with
`java.lang.IllegalStateException: ApplicationSharedMemory not initialized` on the first calls of a
run. `DeviceFacade.get_screen_size` then answered 1080 x 1920 for a 1440 x 3120 screen ("Cannot get
screen dimensions", out-5d, out-5g2, out-5h2, out-r5e, out-r5f of the session), and every gesture
computed in proportion of the screen (the scroll owner reads the size once, when it is built)
covered the upper 60 % of it.

The answer of uiautomator2 is the phone's (`fixtures/u2_device_info_android17_pixel6pro.json`, read
by uiautomator2's own JSON-RPC reader, `_jsonrpc_call`). The screen size, 1440 x 3120, is the one of
every dump of that phone (`[0,0][1440,3120]`); the text of `wm size` is Android's
("Physical size: WxH", an "Override size: WxH" line when one is set), not a capture of that phone.
"""

import json
import subprocess
from typing import Any, cast

import pytest
from uiautomator2 import core as u2_core

from taktik.core.shared.device import screen
from taktik.core.shared.device.facade import BaseDeviceFacade
from unit.paths import CORE

ANDROID_17_DEVICE_INFO = (CORE / "tests/unit/shared/device/fixtures/u2_device_info_android17_pixel6pro.json").read_text(
    encoding="utf-8")
SERIAL = "emulator-5554"


class _Response:
    def __init__(self, body: str):
        self.text = body

    def json(self):
        return json.loads(self.text)


class _Android17Device:
    """A uiautomator2 device whose `info` asks the server for `deviceInfo`, as uiautomator2 does."""

    serial = SERIAL

    @property
    def info(self):
        return u2_core._jsonrpc_call(cast(Any, None), 9008, "deviceInfo", {}, 10, False)


@pytest.fixture
def android_17(monkeypatch):
    monkeypatch.setattr(u2_core, "_http_request", lambda *_a, **_k: _Response(ANDROID_17_DEVICE_INFO))


def _adb_answers(monkeypatch, stdout, returncode=0, stderr=""):
    asked = []

    def run(serial, command, **_kwargs):
        asked.append((serial, command))
        return subprocess.CompletedProcess(["adb"], returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(screen, "run_adb_shell_process", run)
    return asked


def test_the_size_android_17_refuses_comes_from_wm_size(android_17, monkeypatch):
    asked = _adb_answers(monkeypatch, "Physical size: 1440x3120\n")

    assert BaseDeviceFacade(_Android17Device()).get_screen_size() == (1440, 3120)
    assert asked == [(SERIAL, ["wm", "size"])], "wm size goes through the adb door, as words"


def test_the_size_is_read_once_per_facade(android_17, monkeypatch):
    asked = _adb_answers(monkeypatch, "Physical size: 1440x3120\n")
    facade = BaseDeviceFacade(_Android17Device())

    assert facade.get_screen_size() == facade.get_screen_size() == (1440, 3120)
    assert len(asked) == 1


def test_no_size_when_wm_size_fails_too(android_17, monkeypatch):
    _adb_answers(monkeypatch, "", returncode=1, stderr="error: device offline")

    with pytest.raises(screen.ScreenSizeUnreadable, match="ApplicationSharedMemory|IllegalStateException"):
        BaseDeviceFacade(_Android17Device()).get_screen_size()


@pytest.mark.parametrize("output,size", [
    ("Physical size: 1440x3120\n", (1440, 3120)),
    ("Physical size: 1440x3120\nOverride size: 1080x2340\n", (1080, 2340)),
    ("\r\nPhysical size: 1080x2400\r\n", (1080, 2400)),
    ("cmd: Can't find service: window\n", None),
])
def test_wm_size_text(output, size):
    assert screen.parse_wm_size(output) == size
